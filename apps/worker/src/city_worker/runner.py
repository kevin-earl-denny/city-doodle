"""Job runner - uses Postgres LISTEN/NOTIFY for push-based job dispatch.

The worker creates a dedicated asyncpg connection (outside the SQLAlchemy pool)
that LISTENs on the ``new_job`` channel.  When the API inserts a job and sends
``NOTIFY new_job``, the worker wakes up immediately and claims the job.
A 60-second fallback timeout ensures no jobs are permanently stuck even if a
notification is missed.
"""

import asyncio
import json
import logging
import re
import signal
import time
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import asyncpg
from sqlalchemy import text

from city_worker.config import settings
from city_worker.database import get_session
from city_worker.models import JobStatus, JobType
from city_worker.observability import bind_log_context, reset_log_context

logger = logging.getLogger(__name__)


def _make_asyncpg_dsn(sqlalchemy_url: str) -> str:
    """Convert a SQLAlchemy async URL to a plain asyncpg DSN.

    SQLAlchemy URLs use the ``postgresql+asyncpg://`` scheme, but asyncpg
    expects ``postgresql://`` (or ``postgres://``).  We also convert the
    ``sslmode`` query-parameter to ``ssl`` which asyncpg understands.
    """
    dsn = sqlalchemy_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    dsn = re.sub(r"sslmode=(\w+)", r"ssl=\1", dsn)
    return dsn


class _NumpySafeEncoder(json.JSONEncoder):
    """JSON encoder that converts numpy types to native Python types.

    asyncpg cannot serialize numpy scalars (np.float64, np.int64, etc.)
    into JSONB columns. This encoder handles the conversion transparently
    when used with json.dumps().
    """

    def default(self, obj: Any) -> Any:
        try:
            import numpy as np
        except ImportError:
            return super().default(obj)

        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, np.bool_):
            return bool(obj)
        return super().default(obj)


class JobRunner:
    """Listens for new-job notifications and executes them.

    Uses Postgres LISTEN/NOTIFY for push-based wakeup with a configurable
    fallback timeout (default 60 s) so jobs are never permanently stuck.
    """

    CHANNEL = "new_job"

    def __init__(self) -> None:
        self._shutdown = False
        self._active_jobs: set[UUID] = set()
        self._listen_conn: asyncpg.Connection | None = None
        self._notify_event: asyncio.Event = asyncio.Event()
        self._last_reclaim_time: float = 0.0
        self._consecutive_empty_polls: int = 0
        self._current_interval: float = settings.poll_interval_seconds

    def _compute_poll_interval(self) -> float:
        """Compute the next poll interval using exponential backoff.

        Starts at poll_interval_seconds (default 1s), doubles on each
        consecutive empty poll, and caps at max_poll_interval_seconds
        (default 30s). Resets to the base interval when a job is found.
        """
        if self._consecutive_empty_polls == 0:
            return settings.poll_interval_seconds
        base = settings.poll_interval_seconds
        interval = base * (2**self._consecutive_empty_polls)
        return min(interval, settings.max_poll_interval_seconds)

    # ------------------------------------------------------------------
    # LISTEN connection management
    # ------------------------------------------------------------------

    async def _connect_listen(self) -> None:
        """Create (or recreate) the dedicated LISTEN connection."""
        dsn = _make_asyncpg_dsn(settings.database_url)
        try:
            self._listen_conn = await asyncpg.connect(dsn)
            await self._listen_conn.add_listener(self.CHANNEL, self._on_notify)
            logger.info("LISTEN connection established on channel '%s'", self.CHANNEL)
        except Exception:
            logger.exception("Failed to establish LISTEN connection")
            self._listen_conn = None

    async def _close_listen(self) -> None:
        """Cleanly close the LISTEN connection."""
        if self._listen_conn is not None:
            try:
                await self._listen_conn.close()
            except Exception:
                logger.debug("Error closing LISTEN connection", exc_info=True)
            finally:
                self._listen_conn = None

    def _on_notify(
        self,
        connection: asyncpg.Connection,
        pid: int,
        channel: str,
        payload: str,
    ) -> None:
        """Callback invoked by asyncpg when a notification arrives."""
        logger.debug("Received NOTIFY on '%s' (pid=%s)", channel, pid)
        self._notify_event.set()

    async def _ensure_listen(self) -> None:
        """Make sure the LISTEN connection is alive; reconnect if not."""
        if self._listen_conn is not None:
            try:
                # Lightweight health check
                await self._listen_conn.fetchval("SELECT 1")
                return
            except Exception:
                logger.warning("LISTEN connection lost, reconnecting...")
                await self._close_listen()

        await self._connect_listen()

    # ------------------------------------------------------------------
    # Main run loop
    # ------------------------------------------------------------------

    async def run(self) -> None:
        """Main run loop - wait for notifications and process jobs."""
        logger.info("Job runner starting...")
        self._setup_signal_handlers()

        await self._connect_listen()

        while not self._shutdown:
            try:
                # CITY-600: Reclaim stuck jobs periodically
                try:
                    await self._reclaim_stuck_jobs()
                except Exception:
                    logger.exception("Error reclaiming stuck jobs")

                # Ensure LISTEN connection is healthy (reconnect if needed)
                await self._ensure_listen()

                # Wait for a notification OR timeout (safety-net poll)
                self._notify_event.clear()
                try:
                    await asyncio.wait_for(
                        self._notify_event.wait(),
                        timeout=settings.listen_timeout_seconds,
                    )
                    logger.debug("Woke up via NOTIFY")
                except TimeoutError:
                    logger.debug(
                        "Fallback poll (no notification in %.0fs)", settings.listen_timeout_seconds
                    )

                # Drain all available jobs (there may be more than one)
                while not self._shutdown:
                    claimed = await self._poll_and_execute()
                    if not claimed:
                        break

            except Exception:
                logger.exception("Error in job runner loop")
                # Brief back-off before retrying the loop
                await asyncio.sleep(settings.poll_interval_seconds)

        logger.info("Job runner shutting down, waiting for active jobs...")
        await self._close_listen()
        await self._wait_for_active_jobs()
        logger.info("Job runner stopped")

    def _setup_signal_handlers(self) -> None:
        """Set up graceful shutdown on SIGINT/SIGTERM."""
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, self._handle_shutdown)

    def _handle_shutdown(self) -> None:
        """Handle shutdown signal."""
        logger.info("Shutdown signal received")
        self._shutdown = True
        # Wake the event loop so we don't wait for the full listen timeout
        self._notify_event.set()

    async def _wait_for_active_jobs(self, timeout: float = 30.0) -> None:
        """Wait for active jobs to complete with timeout."""
        start = datetime.now(UTC)
        while self._active_jobs:
            elapsed = (datetime.now(UTC) - start).total_seconds()
            if elapsed > timeout:
                logger.warning(
                    "Timeout waiting for jobs to complete, %d jobs still active",
                    len(self._active_jobs),
                )
                break
            await asyncio.sleep(0.5)

    async def _poll_and_execute(self) -> bool:
        """Poll for a pending job and execute it.

        Returns True if a job was found and executed, False otherwise.
        """
        if len(self._active_jobs) >= settings.max_concurrent_jobs:
            return False

        job = await self._claim_job()
        if job is None:
            return False

        job_id, job_type, params = job
        self._active_jobs.add(job_id)
        try:
            await self._execute_job(job_id, job_type, params)
        finally:
            self._active_jobs.discard(job_id)
        return True

    async def _reclaim_stuck_jobs(self) -> None:
        """Reclaim jobs stuck in 'claimed' state past the timeout.

        If a worker crashes after claiming a job but before completing it,
        the job remains in 'claimed' state indefinitely. This method finds
        those stale jobs and sets them back to 'pending' with an incremented
        retry count so another worker can pick them up.

        Jobs that have exhausted their max_retries are marked FAILED instead
        of being re-queued.

        Throttled to run at most once every 60 seconds to reduce DB load.
        """
        now = time.monotonic()
        if now - self._last_reclaim_time < 60.0:
            return
        self._last_reclaim_time = now

        cutoff = datetime.now(UTC) - timedelta(seconds=settings.job_timeout_seconds)
        session = await get_session()
        try:
            async with session.begin():
                result = await session.execute(
                    text("""
                        SELECT id, retry_count, max_retries
                        FROM jobs
                        WHERE status = :claimed
                          AND claimed_at < :cutoff
                        FOR UPDATE SKIP LOCKED
                    """),
                    {
                        "claimed": JobStatus.CLAIMED.value,
                        "cutoff": cutoff,
                    },
                )
                stuck_jobs = result.fetchall()

                for job_id, retry_count, max_retries in stuck_jobs:
                    job_id = UUID(str(job_id))
                    new_retry_count = retry_count + 1

                    if new_retry_count >= max_retries:
                        # Retries exhausted — mark as permanently failed
                        await session.execute(
                            text("""
                                UPDATE jobs
                                SET status = :status,
                                    retry_count = :retry_count,
                                    error = :error,
                                    claimed_at = NULL,
                                    completed_at = :now
                                WHERE id = :job_id
                            """),
                            {
                                "status": JobStatus.FAILED.value,
                                "retry_count": new_retry_count,
                                "error": "Reclaimed: job stuck in claimed state past timeout (max retries exhausted)",
                                "now": datetime.now(UTC),
                                "job_id": job_id,
                            },
                        )
                        logger.warning(
                            "Reclaimed stuck job %s — marked FAILED (retry %d >= max_retries %d)",
                            job_id,
                            new_retry_count,
                            max_retries,
                        )
                    else:
                        delay_seconds = self._compute_retry_delay(retry_count)
                        retry_after = datetime.now(UTC) + timedelta(seconds=delay_seconds)

                        await session.execute(
                            text("""
                                UPDATE jobs
                                SET status = :status,
                                    retry_count = :retry_count,
                                    error = :error,
                                    retry_after = :retry_after,
                                    claimed_at = NULL
                                WHERE id = :job_id
                            """),
                            {
                                "status": JobStatus.PENDING.value,
                                "retry_count": new_retry_count,
                                "error": "Reclaimed: job stuck in claimed state past timeout",
                                "retry_after": retry_after,
                                "job_id": job_id,
                            },
                        )

                        logger.warning(
                            "Reclaimed stuck job %s (retry %d/%d, next retry after %ds)",
                            job_id,
                            new_retry_count,
                            max_retries,
                            delay_seconds,
                        )
        finally:
            await session.close()

    async def _claim_job(self) -> tuple[UUID, str, dict] | None:
        """Claim a pending job using FOR UPDATE SKIP LOCKED.

        Only claims jobs whose retry_after is null or in the past.

        Returns (job_id, job_type, params) or None if no job available.
        """
        session = await get_session()
        try:
            async with session.begin():
                result = await session.execute(
                    text("""
                        SELECT id, type, params
                        FROM jobs
                        WHERE status = :pending
                          AND (retry_after IS NULL OR retry_after <= :now)
                        ORDER BY created_at ASC
                        LIMIT 1
                        FOR UPDATE SKIP LOCKED
                    """),
                    {"pending": JobStatus.PENDING.value, "now": datetime.now(UTC)},
                )
                row = result.fetchone()

                if row is None:
                    return None

                job_id, job_type, params = row
                job_id = UUID(str(job_id))

                await session.execute(
                    text("""
                        UPDATE jobs
                        SET status = :claimed, claimed_at = :now
                        WHERE id = :job_id
                    """),
                    {
                        "claimed": JobStatus.CLAIMED.value,
                        "now": datetime.now(UTC),
                        "job_id": job_id,
                    },
                )

                logger.info("Claimed job %s (type: %s)", job_id, job_type)
                return (job_id, job_type, params or {})
        finally:
            await session.close()

    @staticmethod
    def _compute_retry_delay(retry_count: int) -> int:
        """Compute exponential backoff delay in seconds.

        delay = min(2^retry_count * 30, 300) seconds
        """
        return min(2**retry_count * 30, 300)

    async def _execute_job(self, job_id: UUID, job_type: str, params: dict) -> None:
        """Execute a job and update its status.

        On failure, retries with exponential backoff if retry_count < max_retries.
        After max retries are exhausted, marks the job as permanently FAILED.
        """
        # CITY-642: every line logged during the job carries job_id/job_type/world_id
        # in Axiom; the lifecycle lines below add event/outcome/duration_ms. Stdout
        # format ignores `extra`, so console output is unchanged.
        log_token = bind_log_context(
            job_id=str(job_id),
            job_type=job_type,
            world_id=str(params["world_id"]) if params.get("world_id") else None,
        )
        try:
            await self._execute_job_logged(job_id, job_type, params)
        finally:
            reset_log_context(log_token)

    async def _execute_job_logged(self, job_id: UUID, job_type: str, params: dict) -> None:
        logger.info("Executing job %s (type: %s)", job_id, job_type, extra={"event": "job_started"})
        result: dict[str, Any] | None = None
        error: str | None = None
        start = time.monotonic()

        def lifecycle(event: str, outcome: str, **fields: Any) -> dict[str, Any]:
            return {
                "event": event,
                "outcome": outcome,
                "duration_ms": round((time.monotonic() - start) * 1000, 1),
                **fields,
            }

        try:
            result = await self._run_job_handler(job_id, job_type, params)
            status = JobStatus.COMPLETED
            logger.info(
                "Job %s completed successfully",
                job_id,
                extra=lifecycle("job_finished", "completed"),
            )
        except Exception as e:
            # outcome=error means this attempt failed; whether it is retried is the
            # next line (_retry_job's "Retrying job" or job_failed_permanently below).
            logger.exception("Job %s failed", job_id, extra=lifecycle("job_finished", "error"))
            error = str(e)
            # Check if we can retry
            retry_count, max_retries = await self._get_retry_info(job_id)
            if retry_count < max_retries:
                await self._retry_job(job_id, retry_count, error)
                return
            status = JobStatus.FAILED
            logger.warning(
                "Job %s permanently failed after %d retries",
                job_id,
                retry_count,
                extra={"event": "job_failed_permanently", "retry_count": retry_count},
            )

        await self._update_job_status(job_id, status, result, error)

    async def _run_job_handler(self, job_id: UUID, job_type: str, params: dict) -> dict[str, Any]:
        """Run the appropriate handler for a job type.

        Returns result dict on success, raises on failure.
        """
        handlers = {
            JobType.TERRAIN_GENERATION.value: self._handle_terrain_generation,
            JobType.CITY_GROWTH.value: self._handle_city_growth,
            JobType.GROWTH_SIMULATION.value: self._handle_city_growth,
            JobType.EXPORT_PNG.value: self._handle_export_png,
            JobType.EXPORT_GIF.value: self._handle_export_gif,
        }

        handler = handlers.get(job_type)
        if handler is None:
            raise ValueError(f"Unknown job type: {job_type}")

        return await handler(job_id, params)

    async def _update_job_status(
        self,
        job_id: UUID,
        status: JobStatus,
        result: dict | None,
        error: str | None,
    ) -> None:
        """Update job status in database."""
        session = await get_session()
        try:
            async with session.begin():
                await session.execute(
                    text("""
                        UPDATE jobs
                        SET status = :status,
                            result = :result,
                            error = :error,
                            completed_at = :now
                        WHERE id = :job_id
                    """),
                    {
                        "status": status.value,
                        "result": json.dumps(result, cls=_NumpySafeEncoder) if result else None,
                        "error": error,
                        "now": datetime.now(UTC),
                        "job_id": job_id,
                    },
                )
        finally:
            await session.close()

    async def _update_job_progress(
        self,
        job_id: UUID,
        completed: int,
        total: int,
    ) -> None:
        """Update job progress in database.

        Stores a JSON object like {"completed": 3, "total": 9} in the
        progress column so the frontend can render a progress bar.
        """
        progress = json.dumps({"completed": completed, "total": total})
        session = await get_session()
        try:
            async with session.begin():
                await session.execute(
                    text("""
                        UPDATE jobs
                        SET progress = CAST(:progress AS jsonb)
                        WHERE id = :job_id
                    """),
                    {"progress": progress, "job_id": job_id},
                )
        finally:
            await session.close()

    async def _get_retry_info(self, job_id: UUID) -> tuple[int, int]:
        """Get retry_count and max_retries for a job."""
        session = await get_session()
        try:
            result = await session.execute(
                text("SELECT retry_count, max_retries FROM jobs WHERE id = :job_id"),
                {"job_id": job_id},
            )
            row = result.fetchone()
            if row is None:
                return (0, 3)
            return (row[0], row[1])
        finally:
            await session.close()

    async def _retry_job(self, job_id: UUID, retry_count: int, error: str) -> None:
        """Re-queue a failed job for retry with exponential backoff.

        Increments retry_count, sets status back to PENDING, and schedules
        the retry after an exponential backoff delay.
        """
        new_retry_count = retry_count + 1
        delay_seconds = self._compute_retry_delay(retry_count)
        retry_after = datetime.now(UTC) + timedelta(seconds=delay_seconds)

        logger.info(
            "Retrying job %s (attempt %d) after %ds delay",
            job_id,
            new_retry_count,
            delay_seconds,
            extra={
                "event": "job_retry_scheduled",
                "retry_count": new_retry_count,
                "retry_delay_s": delay_seconds,
            },
        )

        session = await get_session()
        try:
            async with session.begin():
                await session.execute(
                    text("""
                        UPDATE jobs
                        SET status = :status,
                            retry_count = :retry_count,
                            error = :error,
                            retry_after = :retry_after,
                            completed_at = NULL
                        WHERE id = :job_id
                    """),
                    {
                        "status": JobStatus.PENDING.value,
                        "retry_count": new_retry_count,
                        "error": error,
                        "retry_after": retry_after,
                        "job_id": job_id,
                    },
                )
        finally:
            await session.close()

    async def _update_tile_terrain_status(
        self,
        world_id: UUID,
        tx: int,
        ty: int,
        status: str,
        error: str | None = None,
    ) -> None:
        """Update terrain_status for a tile identified by world + coordinates."""
        session = await get_session()
        try:
            async with session.begin():
                values = "terrain_status = :status"
                if error is not None:
                    values += ", terrain_error = :error"
                elif status != "failed":
                    values += ", terrain_error = NULL"
                await session.execute(
                    text(f"""
                        UPDATE tiles
                        SET {values}
                        WHERE world_id = :world_id AND tx = :tx AND ty = :ty
                    """),
                    {"status": status, "error": error, "world_id": world_id, "tx": tx, "ty": ty},
                )
            logger.info(
                "[Terrain] Updated terrain_status=%s for world=%s tx=%s ty=%s",
                status,
                world_id,
                tx,
                ty,
            )
        finally:
            await session.close()

    async def _update_tiles_terrain_status_bulk(
        self,
        world_id: UUID,
        tile_coords: list[tuple[int, int]],
        status: str,
        error: str | None = None,
    ) -> None:
        """Update terrain_status for multiple tiles in a single transaction."""
        session = await get_session()
        try:
            async with session.begin():
                for tx, ty in tile_coords:
                    values = "terrain_status = :status"
                    if error is not None:
                        values += ", terrain_error = :error"
                    elif status != "failed":
                        values += ", terrain_error = NULL"
                    await session.execute(
                        text(f"""
                            UPDATE tiles
                            SET {values}
                            WHERE world_id = :world_id AND tx = :tx AND ty = :ty
                        """),
                        {
                            "status": status,
                            "error": error,
                            "world_id": world_id,
                            "tx": tx,
                            "ty": ty,
                        },
                    )
            logger.info(
                "[Terrain] Bulk updated terrain_status=%s for world=%s (%d tiles)",
                status,
                world_id,
                len(tile_coords),
            )
        finally:
            await session.close()

    async def _handle_terrain_generation(self, job_id: UUID, params: dict) -> dict[str, Any]:
        """Handle terrain generation job.

        Generates terrain for a 3x3 tile neighborhood and saves to database.

        Expected params:
            world_id: UUID of the world
            world_seed: int seed for deterministic generation
            center_tx: int x-coordinate of center tile
            center_ty: int y-coordinate of center tile
            world_settings: dict of world settings (beach_enabled, beach_width_multiplier, etc.)
        """
        from uuid import UUID

        from city_worker.terrain import TerrainConfig, TerrainGenerator, apply_seed_variation

        trace_id = params.get("terrain_trace_id", "unknown")

        # Validate required params
        world_id = params.get("world_id")
        world_seed = params.get("world_seed")
        center_tx = params.get("center_tx", 1)
        center_ty = params.get("center_ty", 1)

        if world_id is None:
            raise ValueError("world_id is required")
        if world_seed is None:
            raise ValueError("world_seed is required")

        world_id = UUID(world_id) if isinstance(world_id, str) else world_id

        # CITY-585: Mark center tile as "generating"
        await self._update_tile_terrain_status(
            world_id, int(center_tx), int(center_ty), "generating"
        )

        # CITY-626: Report initial progress (0/9)
        await self._update_job_progress(job_id, 0, 9)

        try:
            # Extract world settings if provided (from WorldSettings schema)
            world_settings = params.get("world_settings", {})

            # Build terrain config from geographic setting presets + seed variation
            loop = asyncio.get_running_loop()
            geographic_setting = world_settings.get("geographic_setting", "coastal")
            logger.info(
                "[Terrain trace=%s] Job picked up: world=%s setting=%s seed=%s",
                trace_id,
                world_id,
                geographic_setting,
                world_seed,
            )
            config_kwargs = apply_seed_variation(geographic_setting, seed=int(world_seed))
            config_kwargs["world_seed"] = int(world_seed)
            config_kwargs["geographic_setting"] = geographic_setting
            # Explicit per-world overrides take precedence over preset
            if "beach_enabled" in world_settings:
                config_kwargs["beach_enabled"] = world_settings["beach_enabled"]
            if "beach_width_multiplier" in world_settings:
                config_kwargs["beach_width_multiplier"] = world_settings["beach_width_multiplier"]
            config = TerrainConfig(**config_kwargs)
            generator = TerrainGenerator(config)

            t_pipeline_start = time.perf_counter()

            result = await loop.run_in_executor(
                None, generator.generate_3x3, int(center_tx), int(center_ty)
            )

            t_gen_end = time.perf_counter()

            # Save generated tiles to database, reporting progress per tile
            await self._save_terrain_tiles(world_id, result, trace_id, job_id=job_id)

            t_save_end = time.perf_counter()

            gen_s = t_gen_end - t_pipeline_start
            save_s = t_save_end - t_gen_end
            total_s = t_save_end - t_pipeline_start
            logger.info(
                "[Terrain trace=%s] Full pipeline complete in %.1fs (generation=%.1fs save=%.1fs) world=%s setting=%s",
                trace_id,
                total_s,
                gen_s,
                save_s,
                world_id,
                geographic_setting,
            )

            # CITY-585: Mark all generated tiles as "ready"
            all_tiles = result.all_tiles()
            tile_coords = [(t.tx, t.ty) for t in all_tiles]
            await self._update_tiles_terrain_status_bulk(world_id, tile_coords, "ready")

            total_features = sum(len(t.features) for t in all_tiles)

            return {
                "status": "generated",
                "tiles_generated": len(all_tiles),
                "total_features": total_features,
                "center_tile": {"tx": center_tx, "ty": center_ty},
            }
        except Exception as e:
            # CITY-585/590: Mark center tile as "failed" with error message
            logger.exception("[Terrain] Generation failed for world=%s: %s", world_id, str(e))
            try:
                await self._update_tile_terrain_status(
                    world_id, int(center_tx), int(center_ty), "failed", error=str(e)
                )
            except Exception:
                logger.exception("[Terrain] Failed to update terrain_status to 'failed'")
            raise

    async def _save_terrain_tiles(
        self,
        world_id: UUID,
        result: Any,
        trace_id: str = "unknown",
        job_id: UUID | None = None,
    ) -> None:
        """Save generated terrain tiles to the database.

        When job_id is provided, updates the job's progress column after
        each tile is saved so the frontend can show a progress bar.
        """
        from city_worker.terrain import TerrainResult

        result: TerrainResult = result
        all_tiles = result.all_tiles()
        total = len(all_tiles)
        session = await get_session()

        try:
            async with session.begin():
                # CITY-513: Use UPSERT instead of N+1 SELECT+INSERT/UPDATE per tile
                for idx, tile_data in enumerate(all_tiles):
                    terrain_dict = tile_data.to_dict()
                    features_dict = tile_data.features_to_geojson()

                    fc_type = features_dict.get("type") if isinstance(features_dict, dict) else None
                    fc_count = (
                        len(features_dict.get("features", []))
                        if isinstance(features_dict, dict) and fc_type == "FeatureCollection"
                        else 0
                    )
                    logger.info(
                        "[Terrain trace=%s] Saving tile tx=%s ty=%s feature_count=%d",
                        trace_id,
                        tile_data.tx,
                        tile_data.ty,
                        fc_count,
                    )

                    # CITY-612: Serialize dicts to JSON strings for JSONB columns.
                    # Use _NumpySafeEncoder to convert any numpy scalars (np.float64,
                    # np.int64, etc.) that Shapely/numpy leave in the geometry
                    # coordinates and properties.
                    terrain_json = json.dumps(terrain_dict, cls=_NumpySafeEncoder)
                    features_json = json.dumps(features_dict, cls=_NumpySafeEncoder)

                    await session.execute(
                        text("""
                            INSERT INTO tiles (id, world_id, tx, ty, terrain_data, features, terrain_status, version)
                            VALUES (gen_random_uuid(), :world_id, :tx, :ty, CAST(:terrain_data AS jsonb), CAST(:features AS jsonb), 'ready', 1)
                            ON CONFLICT (world_id, tx, ty)
                            DO UPDATE SET
                                terrain_data = EXCLUDED.terrain_data,
                                features = EXCLUDED.features,
                                terrain_status = 'ready',
                                terrain_error = NULL,
                                version = tiles.version + 1,
                                updated_at = now()
                        """),
                        {
                            "world_id": world_id,
                            "tx": tile_data.tx,
                            "ty": tile_data.ty,
                            "terrain_data": terrain_json,
                            "features": features_json,
                        },
                    )

                logger.info(
                    "[Terrain trace=%s] Saved %d terrain tiles for world %s",
                    trace_id,
                    total,
                    world_id,
                )

            # CITY-626: Report progress after the transaction commits
            # so the frontend sees a consistent state.
            if job_id is not None:
                await self._update_job_progress(job_id, total, total)
        finally:
            await session.close()

    async def _handle_city_growth(self, job_id: UUID, params: dict) -> dict[str, Any]:
        """Handle city growth simulation job.

        Simulates city growth over 1/5/10 year steps:
        - Infill development in existing districts
        - Expansion at district edges
        - New road connections
        - New supporting POIs
        - Respects historic district flag (no changes)

        Expected params:
            world_id: UUID of the world
            years: int time steps to simulate (1, 5, or 10)
        """
        from uuid import UUID

        from city_worker.growth import GrowthConfig, GrowthSimulator

        logger.info("City growth job with params: %s", params)

        # Validate params
        world_id = params.get("world_id")
        years = params.get("years", 1)
        if world_id is None:
            raise ValueError("world_id is required")

        world_id = UUID(world_id) if isinstance(world_id, str) else world_id
        years = max(1, min(int(years), 10))

        # Fetch current world state from DB
        districts, road_nodes, road_edges, pois, world_seed = await self._load_world_state(world_id)

        if not districts:
            return {
                "status": "skipped",
                "message": "No districts found in world",
                "changelog": {"entries": [], "summary": {}},
            }

        # Load water regions from terrain for expansion constraints
        water_regions = await self._load_water_regions(world_id)

        # Load transit stations for TOD growth (CITY-314)
        transit_stations = await self._load_transit_stations(world_id)

        # Run simulation
        config = GrowthConfig(world_id=world_id, years=years)
        simulator = GrowthSimulator(config, seed=world_seed)
        changelog = simulator.simulate(
            districts,
            road_nodes,
            road_edges,
            pois,
            water_regions,
            transit_stations,
        )

        # Persist changes back to DB
        await self._save_growth_results(
            world_id,
            districts,
            road_nodes,
            road_edges,
            pois,
            changelog,
        )

        result = changelog.to_dict()
        result["status"] = "simulated"
        return result

    async def _load_world_state(
        self,
        world_id: UUID,
    ) -> tuple[list[dict], list[dict], list[dict], list[dict], int]:
        """Load districts, road nodes, road edges, POIs, and world seed."""
        session = await get_session()
        try:
            # Get world seed
            result = await session.execute(
                text("SELECT seed FROM worlds WHERE id = :wid"),
                {"wid": world_id},
            )
            row = result.fetchone()
            world_seed = row[0] if row else 0

            # Fetch districts
            result = await session.execute(
                text("""
                    SELECT id, world_id, type, name, geometry, density,
                           max_height, transit_access, historic
                    FROM districts WHERE world_id = :wid
                """),
                {"wid": world_id},
            )
            districts = [
                {
                    "id": str(r[0]),
                    "world_id": str(r[1]),
                    "type": r[2],
                    "name": r[3],
                    "geometry": r[4],
                    "density": float(r[5]),
                    "max_height": r[6],
                    "transit_access": r[7],
                    "historic": r[8],
                }
                for r in result.fetchall()
            ]

            # Fetch road nodes
            result = await session.execute(
                text("""
                    SELECT id, world_id, position, node_type, name
                    FROM road_nodes WHERE world_id = :wid
                """),
                {"wid": world_id},
            )
            road_nodes = [
                {
                    "id": str(r[0]),
                    "world_id": str(r[1]),
                    "position": r[2],
                    "node_type": r[3],
                    "name": r[4],
                }
                for r in result.fetchall()
            ]

            # Fetch road edges
            result = await session.execute(
                text("""
                    SELECT id, world_id, from_node_id, to_node_id, road_class,
                           geometry, length_meters, speed_limit, name,
                           is_one_way, lanes, district_id
                    FROM road_edges WHERE world_id = :wid
                """),
                {"wid": world_id},
            )
            road_edges = [
                {
                    "id": str(r[0]),
                    "world_id": str(r[1]),
                    "from_node_id": str(r[2]),
                    "to_node_id": str(r[3]),
                    "road_class": r[4],
                    "geometry": r[5],
                    "length_meters": float(r[6]) if r[6] else 0,
                    "speed_limit": r[7],
                    "name": r[8],
                    "is_one_way": r[9],
                    "lanes": r[10],
                    "district_id": str(r[11]) if r[11] else None,
                }
                for r in result.fetchall()
            ]

            # Fetch POIs
            result = await session.execute(
                text("""
                    SELECT id, world_id, type, name, position_x, position_y
                    FROM pois WHERE world_id = :wid
                """),
                {"wid": world_id},
            )
            pois = [
                {
                    "id": str(r[0]),
                    "world_id": str(r[1]),
                    "type": r[2],
                    "name": r[3],
                    "position_x": float(r[4]),
                    "position_y": float(r[5]),
                }
                for r in result.fetchall()
            ]

            return districts, road_nodes, road_edges, pois, world_seed
        finally:
            await session.close()

    async def _load_transit_stations(self, world_id: UUID) -> list[dict]:
        """Load transit station positions for TOD growth calculations."""
        session = await get_session()
        try:
            result = await session.execute(
                text("""
                    SELECT id, position_x, position_y, station_type
                    FROM transit_stations WHERE world_id = :wid
                """),
                {"wid": world_id},
            )
            return [
                {
                    "id": str(r[0]),
                    "position_x": float(r[1]),
                    "position_y": float(r[2]),
                    "station_type": r[3],
                }
                for r in result.fetchall()
            ]
        finally:
            await session.close()

    async def _load_water_regions(self, world_id: UUID) -> list[dict]:
        """Load water region geometries from terrain tiles for this world.

        Extracts coastline, lake, bay, and lagoon features from terrain data
        so the growth simulator can avoid expanding districts into water.
        """
        session = await get_session()
        try:
            result = await session.execute(
                text("""
                    SELECT terrain_data FROM tiles
                    WHERE world_id = :wid AND terrain_data IS NOT NULL
                """),
                {"wid": world_id},
            )
            water_types = {"coastline", "lake", "bay", "lagoon"}
            water_regions: list[dict] = []
            for (terrain_data,) in result.fetchall():
                if not terrain_data:
                    continue
                # terrain_data may be stored as JSON string or dict
                data = json.loads(terrain_data) if isinstance(terrain_data, str) else terrain_data
                features = data.get("features", [])
                for feat in features:
                    feat_type = feat.get("type", "")
                    geom = feat.get("geometry")
                    if feat_type in water_types and geom:
                        water_regions.append({"type": feat_type, "geometry": geom})
            return water_regions
        finally:
            await session.close()

    async def _save_growth_results(
        self,
        world_id: UUID,
        districts: list[dict],
        road_nodes: list[dict],
        road_edges: list[dict],
        pois: list[dict],
        changelog: Any,
    ) -> None:
        """Persist growth simulation results to the database."""
        session = await get_session()
        try:
            async with session.begin():
                now = datetime.now(UTC)

                # Update districts (density, max_height, geometry)
                for entry in changelog.entries:
                    if entry.entity_type != "district":
                        continue

                    district = next(
                        (d for d in districts if str(d["id"]) == entry.entity_id),
                        None,
                    )
                    if district is None:
                        continue

                    await session.execute(
                        text("""
                            UPDATE districts
                            SET density = :density,
                                max_height = :max_height,
                                geometry = :geometry,
                                updated_at = :now
                            WHERE id = :did
                        """),
                        {
                            "density": district["density"],
                            "max_height": district["max_height"],
                            "geometry": district["geometry"],
                            "now": now,
                            "did": district["id"],
                        },
                    )

                # Insert new road nodes
                for entry in changelog.entries:
                    if entry.entity_type != "road_node":
                        continue

                    node = next(
                        (n for n in road_nodes if str(n["id"]) == entry.entity_id),
                        None,
                    )
                    if node is None:
                        continue

                    await session.execute(
                        text("""
                            INSERT INTO road_nodes
                                (id, world_id, position, node_type, name)
                            VALUES
                                (:id, :world_id, :position, :node_type, :name)
                        """),
                        {
                            "id": node["id"],
                            "world_id": world_id,
                            "position": node["position"],
                            "node_type": node["node_type"],
                            "name": node.get("name"),
                        },
                    )

                # Insert new road edges
                for entry in changelog.entries:
                    if entry.entity_type != "road_edge":
                        continue

                    edge = next(
                        (e for e in road_edges if str(e["id"]) == entry.entity_id),
                        None,
                    )
                    if edge is None:
                        continue

                    await session.execute(
                        text("""
                            INSERT INTO road_edges
                                (id, world_id, from_node_id, to_node_id,
                                 road_class, geometry, length_meters,
                                 speed_limit, name, is_one_way, lanes, district_id)
                            VALUES
                                (:id, :world_id, :from_node_id, :to_node_id,
                                 :road_class, :geometry, :length_meters,
                                 :speed_limit, :name, :is_one_way, :lanes, :district_id)
                        """),
                        {
                            "id": edge["id"],
                            "world_id": world_id,
                            "from_node_id": edge["from_node_id"],
                            "to_node_id": edge["to_node_id"],
                            "road_class": edge["road_class"],
                            "geometry": edge.get("geometry", []),
                            "length_meters": edge.get("length_meters", 0),
                            "speed_limit": edge.get("speed_limit"),
                            "name": edge.get("name"),
                            "is_one_way": edge.get("is_one_way", False),
                            "lanes": edge.get("lanes", 2),
                            "district_id": edge.get("district_id"),
                        },
                    )

                # Insert new POIs
                for entry in changelog.entries:
                    if entry.entity_type != "poi":
                        continue

                    poi = next(
                        (p for p in pois if str(p["id"]) == entry.entity_id),
                        None,
                    )
                    if poi is None:
                        continue

                    await session.execute(
                        text("""
                            INSERT INTO pois
                                (id, world_id, type, name, position_x, position_y)
                            VALUES
                                (:id, :world_id, :type, :name, :position_x, :position_y)
                        """),
                        {
                            "id": poi["id"],
                            "world_id": world_id,
                            "type": poi["type"],
                            "name": poi["name"],
                            "position_x": poi["position_x"],
                            "position_y": poi["position_y"],
                        },
                    )

                logger.info(
                    "Saved growth results for world %s: %d infilled, %d expanded, "
                    "%d roads, %d POIs",
                    world_id,
                    changelog.districts_infilled,
                    changelog.districts_expanded,
                    changelog.roads_added,
                    changelog.pois_added,
                )
        finally:
            await session.close()

    async def _handle_export_png(self, job_id: UUID, params: dict) -> dict[str, Any]:
        """Handle PNG export job.

        Placeholder - will be implemented later.
        """
        logger.info("PNG export job with params: %s", params)
        await asyncio.sleep(0.1)
        return {"status": "exported", "message": "PNG export not yet implemented"}

    async def _handle_export_gif(self, job_id: UUID, params: dict) -> dict[str, Any]:
        """Handle GIF export job.

        Placeholder - will be implemented later.
        """
        logger.info("GIF export job with params: %s", params)
        await asyncio.sleep(0.1)
        return {"status": "exported", "message": "GIF export not yet implemented"}
