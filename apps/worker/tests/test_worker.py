"""Tests for worker module."""

import asyncio
from contextlib import ExitStack, contextmanager
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from city_worker.config import Settings
from city_worker.models import JobStatus, JobType
from city_worker.runner import JobRunner, _make_asyncpg_dsn

# Runner methods that touch the database; handlers call these, so unit tests
# stub them all (CITY-626 added progress/status writes inside the handlers).
_DB_WRITE_METHODS = (
    "_save_terrain_tiles",
    "_update_tile_terrain_status",
    "_update_tiles_terrain_status_bulk",
    "_update_job_progress",
    "_save_growth_results",
)


@contextmanager
def no_db(runner, world_state=([], [], [], [], 42)):
    """Stub every DB read/write a job handler makes."""
    with ExitStack() as stack:
        for name in _DB_WRITE_METHODS:
            stack.enter_context(patch.object(runner, name, new_callable=AsyncMock))
        stack.enter_context(
            patch.object(
                runner, "_load_world_state", new_callable=AsyncMock, return_value=world_state
            )
        )
        for name in ("_load_transit_stations", "_load_water_regions"):
            stack.enter_context(patch.object(runner, name, new_callable=AsyncMock, return_value=[]))
        yield


def test_job_status_values():
    """Test JobStatus enum has expected values."""
    assert JobStatus.PENDING.value == "pending"
    assert JobStatus.RUNNING.value == "running"
    assert JobStatus.CLAIMED.value == "claimed"
    assert JobStatus.COMPLETED.value == "completed"
    assert JobStatus.FAILED.value == "failed"
    assert JobStatus.CANCELLED.value == "cancelled"


def test_job_type_values():
    """Test JobType enum has expected values."""
    assert JobType.TERRAIN_GENERATION.value == "terrain_generation"
    assert JobType.SEED_PLACEMENT.value == "seed_placement"
    assert JobType.GROWTH_SIMULATION.value == "growth_simulation"
    assert JobType.VMT_CALCULATION.value == "vmt_calculation"
    assert JobType.CITY_GROWTH.value == "city_growth"
    assert JobType.EXPORT_PNG.value == "export_png"
    assert JobType.EXPORT_GIF.value == "export_gif"


def test_settings_defaults():
    """Test Settings has sensible defaults."""
    settings = Settings()
    assert settings.poll_interval_seconds > 0
    assert settings.max_concurrent_jobs > 0
    assert settings.job_timeout_seconds > 0


def test_job_runner_initialization():
    """Test JobRunner initializes correctly."""
    runner = JobRunner()
    assert runner._shutdown is False
    assert len(runner._active_jobs) == 0


def test_job_runner_shutdown_handler():
    """Test JobRunner handles shutdown signal."""
    runner = JobRunner()
    assert runner._shutdown is False

    runner._handle_shutdown()

    assert runner._shutdown is True


@pytest.mark.asyncio
async def test_job_handler_terrain_generation():
    """Test terrain generation handler returns expected result."""
    runner = JobRunner()

    with no_db(runner):
        result = await runner._handle_terrain_generation(
            uuid4(),
            {
                "world_id": str(uuid4()),
                "world_seed": 42,
                "center_tx": 0,
                "center_ty": 0,
            },
        )

    assert "status" in result
    assert result["status"] == "generated"
    assert result["tiles_generated"] == 9


@pytest.mark.asyncio
async def test_job_handler_terrain_generation_missing_params():
    """Test terrain generation handler validates required params."""
    runner = JobRunner()

    with pytest.raises(ValueError, match="world_id is required"):
        await runner._handle_terrain_generation(uuid4(), {})

    with pytest.raises(ValueError, match="world_seed is required"):
        await runner._handle_terrain_generation(uuid4(), {"world_id": str(uuid4())})


@pytest.mark.asyncio
async def test_job_handler_city_growth():
    """Test city growth handler returns expected result."""
    runner = JobRunner()
    world_id = str(uuid4())

    # Mock _load_world_state and _save_growth_results to avoid DB
    districts = [
        {
            "id": str(uuid4()),
            "world_id": world_id,
            "type": "residential",
            "name": "Test District",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[0, 0], [1000, 0], [1000, 1000], [0, 1000], [0, 0]]],
            },
            "density": 3.0,
            "max_height": 8,
            "transit_access": False,
            "historic": False,
        }
    ]
    with no_db(runner, world_state=(districts, [], [], [], 42)):
        result = await runner._handle_city_growth(
            uuid4(),
            {"world_id": world_id, "years": 1},
        )

    assert "status" in result
    assert result["status"] == "simulated"
    assert "summary" in result


@pytest.mark.asyncio
async def test_job_handler_export_png():
    """Test PNG export handler returns expected result."""
    runner = JobRunner()
    result = await runner._handle_export_png(uuid4(), {})

    assert "status" in result
    assert result["status"] == "exported"


@pytest.mark.asyncio
async def test_job_handler_export_gif():
    """Test GIF export handler returns expected result."""
    runner = JobRunner()
    result = await runner._handle_export_gif(uuid4(), {})

    assert "status" in result
    assert result["status"] == "exported"


@pytest.mark.asyncio
async def test_run_job_handler_unknown_type():
    """Test that unknown job type raises ValueError."""
    runner = JobRunner()

    with pytest.raises(ValueError, match="Unknown job type"):
        await runner._run_job_handler(uuid4(), "unknown_type", {})


@pytest.mark.asyncio
async def test_run_job_handler_valid_types():
    """Test that implemented job types are handled."""
    runner = JobRunner()

    # Test export job types that don't require complex params
    simple_types = [
        JobType.EXPORT_PNG,
        JobType.EXPORT_GIF,
    ]

    for job_type in simple_types:
        result = await runner._run_job_handler(uuid4(), job_type.value, {})
        assert isinstance(result, dict)
        assert "status" in result

    # Test terrain generation with required params
    with no_db(runner):
        result = await runner._run_job_handler(
            uuid4(),
            JobType.TERRAIN_GENERATION.value,
            {"world_id": str(uuid4()), "world_seed": 42, "center_tx": 0, "center_ty": 0},
        )
        assert isinstance(result, dict)
        assert "status" in result

    # Test city growth with required params and mocked DB
    world_id = str(uuid4())
    with no_db(runner):
        result = await runner._run_job_handler(
            uuid4(),
            JobType.CITY_GROWTH.value,
            {"world_id": world_id},
        )
        assert isinstance(result, dict)
        assert "status" in result


# ============================================================================
# Additional Tests
# ============================================================================


def test_job_status_is_string_enum():
    """Test JobStatus values work as strings."""
    assert JobStatus.PENDING == "pending"
    assert JobStatus.COMPLETED.value == "completed"
    # Can be used in string contexts via .value
    assert f"Status: {JobStatus.FAILED.value}" == "Status: failed"


def test_job_type_is_string_enum():
    """Test JobType values work as strings."""
    assert JobType.TERRAIN_GENERATION == "terrain_generation"
    assert JobType.CITY_GROWTH.value == "city_growth"


def test_settings_custom_values():
    """Test Settings accepts custom values."""
    settings = Settings(
        poll_interval_seconds=5.0,
        max_concurrent_jobs=4,
        job_timeout_seconds=600,
    )
    assert settings.poll_interval_seconds == 5.0
    assert settings.max_concurrent_jobs == 4
    assert settings.job_timeout_seconds == 600


def test_job_runner_active_jobs_tracking():
    """Test JobRunner tracks active jobs correctly."""
    runner = JobRunner()
    job_id = uuid4()

    assert job_id not in runner._active_jobs

    runner._active_jobs.add(job_id)
    assert job_id in runner._active_jobs
    assert len(runner._active_jobs) == 1

    runner._active_jobs.discard(job_id)
    assert job_id not in runner._active_jobs
    assert len(runner._active_jobs) == 0


@pytest.mark.asyncio
async def test_wait_for_active_jobs_completes_when_empty():
    """Test _wait_for_active_jobs returns immediately when no active jobs."""
    runner = JobRunner()
    # Should complete almost immediately since there are no active jobs
    await asyncio.wait_for(runner._wait_for_active_jobs(timeout=1.0), timeout=0.5)


@pytest.mark.asyncio
async def test_wait_for_active_jobs_waits_for_jobs():
    """Test _wait_for_active_jobs waits while jobs are active."""
    runner = JobRunner()
    job_id = uuid4()
    runner._active_jobs.add(job_id)

    async def clear_job_after_delay():
        await asyncio.sleep(0.2)
        runner._active_jobs.discard(job_id)

    # Start task to clear job
    task = asyncio.create_task(clear_job_after_delay())

    # Wait should complete after job is cleared
    await runner._wait_for_active_jobs(timeout=1.0)

    await task
    assert len(runner._active_jobs) == 0


@pytest.mark.asyncio
async def test_wait_for_active_jobs_timeout():
    """Test _wait_for_active_jobs times out with stuck jobs."""
    runner = JobRunner()
    job_id = uuid4()
    runner._active_jobs.add(job_id)

    # Should timeout without clearing the job
    await runner._wait_for_active_jobs(timeout=0.3)

    # Job should still be in active set after timeout
    assert job_id in runner._active_jobs


@pytest.mark.asyncio
async def test_job_handler_with_params():
    """Test job handlers receive and can use params."""
    runner = JobRunner()
    params = {
        "world_id": str(uuid4()),
        "world_seed": 12345,
        "center_tx": 5,
        "center_ty": 3,
    }

    with no_db(runner):
        result = await runner._handle_terrain_generation(uuid4(), params)

    assert result is not None
    assert "status" in result
    assert result["center_tile"]["tx"] == 5
    assert result["center_tile"]["ty"] == 3


@pytest.mark.asyncio
async def test_execute_job_success():
    """Test _execute_job completes successfully."""
    runner = JobRunner()
    job_id = uuid4()
    params = {
        "world_id": str(uuid4()),
        "world_seed": 42,
        "center_tx": 0,
        "center_ty": 0,
    }

    with (
        no_db(runner),
        patch.object(runner, "_update_job_status", new_callable=AsyncMock) as mock_update,
    ):
        await runner._execute_job(job_id, JobType.TERRAIN_GENERATION.value, params)

        mock_update.assert_called_once()
        call_args = mock_update.call_args
        assert call_args[0][0] == job_id
        assert call_args[0][1] == JobStatus.COMPLETED


@pytest.mark.asyncio
async def test_execute_job_failure_exhausted_retries():
    """Test _execute_job marks as FAILED when retries are exhausted."""
    runner = JobRunner()
    job_id = uuid4()

    # Mock handler to raise exception, retries exhausted (retry_count=3, max_retries=3)
    with (
        patch.object(runner, "_run_job_handler", side_effect=Exception("Test error")),
        patch.object(runner, "_get_retry_info", new_callable=AsyncMock, return_value=(3, 3)),
        patch.object(runner, "_update_job_status", new_callable=AsyncMock) as mock_update,
    ):
        await runner._execute_job(job_id, JobType.TERRAIN_GENERATION.value, {})

        mock_update.assert_called_once()
        call_args = mock_update.call_args
        assert call_args[0][0] == job_id
        assert call_args[0][1] == JobStatus.FAILED
        assert "Test error" in call_args[0][3]


@pytest.mark.asyncio
async def test_execute_job_failure_retries_remaining():
    """Test _execute_job retries when retry_count < max_retries."""
    runner = JobRunner()
    job_id = uuid4()

    # Mock handler to raise exception, retries remaining (retry_count=0, max_retries=3)
    with (
        patch.object(runner, "_run_job_handler", side_effect=Exception("Transient error")),
        patch.object(runner, "_get_retry_info", new_callable=AsyncMock, return_value=(0, 3)),
        patch.object(runner, "_retry_job", new_callable=AsyncMock) as mock_retry,
        patch.object(runner, "_update_job_status", new_callable=AsyncMock) as mock_update,
    ):
        await runner._execute_job(job_id, JobType.TERRAIN_GENERATION.value, {})

        # Should retry, not mark as failed
        mock_retry.assert_called_once_with(job_id, 0, "Transient error")
        mock_update.assert_not_called()


@pytest.mark.asyncio
async def test_execute_job_failure_second_retry():
    """Test _execute_job retries on second attempt when retries remaining."""
    runner = JobRunner()
    job_id = uuid4()

    # retry_count=1, max_retries=3 means 2 more retries available
    with (
        patch.object(runner, "_run_job_handler", side_effect=Exception("DB timeout")),
        patch.object(runner, "_get_retry_info", new_callable=AsyncMock, return_value=(1, 3)),
        patch.object(runner, "_retry_job", new_callable=AsyncMock) as mock_retry,
        patch.object(runner, "_update_job_status", new_callable=AsyncMock) as mock_update,
    ):
        await runner._execute_job(job_id, JobType.TERRAIN_GENERATION.value, {})

        mock_retry.assert_called_once_with(job_id, 1, "DB timeout")
        mock_update.assert_not_called()


@pytest.mark.asyncio
async def test_poll_and_execute_respects_max_concurrent():
    """Test _poll_and_execute respects max concurrent jobs limit."""
    runner = JobRunner()

    # Fill up active jobs to max
    from city_worker.config import settings

    for _ in range(settings.max_concurrent_jobs):
        runner._active_jobs.add(uuid4())

    # Mock _claim_job - should not be called when at max capacity
    with patch.object(runner, "_claim_job", new_callable=AsyncMock) as mock_claim:
        await runner._poll_and_execute()
        mock_claim.assert_not_called()


@pytest.mark.asyncio
async def test_poll_and_execute_no_job_available():
    """Test _poll_and_execute handles no available jobs and returns False."""
    runner = JobRunner()

    # Mock _claim_job to return None (no jobs)
    with patch.object(runner, "_claim_job", new_callable=AsyncMock, return_value=None):
        result = await runner._poll_and_execute()
        assert result is False
        assert len(runner._active_jobs) == 0


@pytest.mark.asyncio
async def test_poll_and_execute_returns_true_when_job_found():
    """Test _poll_and_execute returns True when a job is claimed and executed."""
    runner = JobRunner()
    job_id = uuid4()

    with (
        patch.object(
            runner,
            "_claim_job",
            new_callable=AsyncMock,
            return_value=(job_id, "export_png", {}),
        ),
        patch.object(runner, "_execute_job", new_callable=AsyncMock),
    ):
        result = await runner._poll_and_execute()
        assert result is True


# ============================================================================
# Retry Logic Tests
# ============================================================================


def test_compute_retry_delay_first_attempt():
    """Test exponential backoff: first retry = 30 seconds."""
    assert JobRunner._compute_retry_delay(0) == 30


def test_compute_retry_delay_second_attempt():
    """Test exponential backoff: second retry = 60 seconds."""
    assert JobRunner._compute_retry_delay(1) == 60


def test_compute_retry_delay_third_attempt():
    """Test exponential backoff: third retry = 120 seconds."""
    assert JobRunner._compute_retry_delay(2) == 120


def test_compute_retry_delay_capped_at_300():
    """Test exponential backoff caps at 300 seconds."""
    assert JobRunner._compute_retry_delay(4) == 300
    assert JobRunner._compute_retry_delay(10) == 300
    assert JobRunner._compute_retry_delay(100) == 300


def test_compute_retry_delay_progression():
    """Test the full delay progression follows 2^n * 30, capped at 300."""
    expected = [30, 60, 120, 240, 300]
    for i, exp in enumerate(expected):
        assert JobRunner._compute_retry_delay(i) == exp


# ============================================================================
# LISTEN/NOTIFY Tests (CITY-605)
# ============================================================================


def test_make_asyncpg_dsn_strips_driver():
    """Test _make_asyncpg_dsn converts SQLAlchemy URL to asyncpg DSN."""
    url = "postgresql+asyncpg://user:pass@host:5432/db"
    assert _make_asyncpg_dsn(url) == "postgresql://user:pass@host:5432/db"


def test_make_asyncpg_dsn_converts_sslmode():
    """Test _make_asyncpg_dsn converts sslmode to ssl."""
    url = "postgresql+asyncpg://host/db?sslmode=require"
    assert _make_asyncpg_dsn(url) == "postgresql://host/db?ssl=require"


def test_make_asyncpg_dsn_full():
    """Test _make_asyncpg_dsn handles both driver and sslmode."""
    url = "postgresql+asyncpg://user:pass@host:5432/db?sslmode=require"
    assert _make_asyncpg_dsn(url) == "postgresql://user:pass@host:5432/db?ssl=require"


def test_make_asyncpg_dsn_no_changes_needed():
    """Test _make_asyncpg_dsn passes through plain postgres URLs."""
    url = "postgresql://host/db"
    assert _make_asyncpg_dsn(url) == "postgresql://host/db"


def test_settings_listen_timeout_default():
    """Test Settings has listen_timeout_seconds with correct default."""
    s = Settings()
    assert s.listen_timeout_seconds == 60.0


def test_settings_listen_timeout_custom():
    """Test Settings accepts custom listen_timeout_seconds."""
    s = Settings(listen_timeout_seconds=30.0)
    assert s.listen_timeout_seconds == 30.0


def test_job_runner_has_listen_fields():
    """Test JobRunner initializes with LISTEN/NOTIFY fields."""
    runner = JobRunner()
    assert runner._listen_conn is None
    assert isinstance(runner._notify_event, asyncio.Event)
    assert not runner._notify_event.is_set()


def test_on_notify_sets_event():
    """Test _on_notify callback sets the notify event."""
    runner = JobRunner()
    assert not runner._notify_event.is_set()

    # Simulate a notification callback
    runner._on_notify(MagicMock(), 12345, "new_job", "")

    assert runner._notify_event.is_set()


def test_shutdown_sets_notify_event():
    """Test _handle_shutdown sets the notify event to wake the loop."""
    runner = JobRunner()
    assert not runner._notify_event.is_set()

    runner._handle_shutdown()

    assert runner._shutdown is True
    assert runner._notify_event.is_set()


@pytest.mark.asyncio
async def test_poll_and_execute_returns_false_when_no_jobs():
    """Test _poll_and_execute returns False when no jobs are available."""
    runner = JobRunner()
    with patch.object(runner, "_claim_job", new_callable=AsyncMock, return_value=None):
        result = await runner._poll_and_execute()
        assert result is False


@pytest.mark.asyncio
async def test_poll_and_execute_returns_true_when_job_claimed():
    """Test _poll_and_execute returns True when a job is claimed."""
    runner = JobRunner()
    job_id = uuid4()

    with (
        patch.object(
            runner,
            "_claim_job",
            new_callable=AsyncMock,
            return_value=(job_id, "export_png", {}),
        ),
        patch.object(runner, "_execute_job", new_callable=AsyncMock),
    ):
        result = await runner._poll_and_execute()
        assert result is True


@pytest.mark.asyncio
async def test_poll_and_execute_returns_false_at_capacity():
    """Test _poll_and_execute returns False when at max capacity."""
    runner = JobRunner()
    from city_worker.config import settings

    for _ in range(settings.max_concurrent_jobs):
        runner._active_jobs.add(uuid4())

    result = await runner._poll_and_execute()
    assert result is False


# ============================================================================
# Poll Interval Backoff Tests (CITY-603)
# ============================================================================


def test_poll_interval_starts_at_base():
    """Test poll interval starts at the base poll_interval_seconds."""
    runner = JobRunner()
    assert runner._consecutive_empty_polls == 0
    assert runner._current_interval == 1.0
    assert runner._compute_poll_interval() == 1.0


def test_poll_interval_doubles_on_empty_poll():
    """Test poll interval doubles with consecutive empty polls."""
    runner = JobRunner()
    runner._consecutive_empty_polls = 1
    assert runner._compute_poll_interval() == 2.0
    runner._consecutive_empty_polls = 2
    assert runner._compute_poll_interval() == 4.0
    runner._consecutive_empty_polls = 3
    assert runner._compute_poll_interval() == 8.0
    runner._consecutive_empty_polls = 4
    assert runner._compute_poll_interval() == 16.0


def test_poll_interval_caps_at_max():
    """Test poll interval caps at max_poll_interval_seconds (default 30s)."""
    runner = JobRunner()
    runner._consecutive_empty_polls = 5
    assert runner._compute_poll_interval() == 30.0  # 1 * 2^5 = 32, capped to 30
    runner._consecutive_empty_polls = 10
    assert runner._compute_poll_interval() == 30.0
    runner._consecutive_empty_polls = 100
    assert runner._compute_poll_interval() == 30.0


def test_poll_interval_resets_on_zero_empty_polls():
    """Test poll interval resets to base when empty polls counter is zero."""
    runner = JobRunner()
    runner._consecutive_empty_polls = 5
    assert runner._compute_poll_interval() == 30.0

    runner._consecutive_empty_polls = 0
    assert runner._compute_poll_interval() == 1.0


def test_poll_interval_progression():
    """Test the full backoff progression: 1 -> 2 -> 4 -> 8 -> 16 -> 30 -> 30."""
    runner = JobRunner()
    expected = [1.0, 2.0, 4.0, 8.0, 16.0, 30.0, 30.0]
    for i, exp in enumerate(expected):
        runner._consecutive_empty_polls = i
        assert runner._compute_poll_interval() == exp, (
            f"At empty_polls={i}, expected {exp}, got {runner._compute_poll_interval()}"
        )


def test_poll_interval_respects_custom_max():
    """Test poll interval respects a custom max_poll_interval_seconds."""
    with patch("city_worker.runner.settings") as mock_settings:
        mock_settings.poll_interval_seconds = 1.0
        mock_settings.max_poll_interval_seconds = 10.0
        mock_settings.max_concurrent_jobs = 2

        runner = JobRunner()
        runner._consecutive_empty_polls = 5
        # 1 * 2^5 = 32, but capped to custom max of 10
        assert runner._compute_poll_interval() == 10.0


def test_poll_interval_respects_custom_base():
    """Test poll interval respects a custom poll_interval_seconds base."""
    with patch("city_worker.runner.settings") as mock_settings:
        mock_settings.poll_interval_seconds = 2.0
        mock_settings.max_poll_interval_seconds = 60.0
        mock_settings.max_concurrent_jobs = 2

        runner = JobRunner()
        runner._consecutive_empty_polls = 0
        assert runner._compute_poll_interval() == 2.0
        runner._consecutive_empty_polls = 1
        assert runner._compute_poll_interval() == 4.0
        runner._consecutive_empty_polls = 2
        assert runner._compute_poll_interval() == 8.0


def test_job_runner_initializes_backoff_state():
    """Test JobRunner initializes backoff state correctly."""
    runner = JobRunner()
    assert runner._consecutive_empty_polls == 0
    assert runner._current_interval == 1.0


def test_settings_max_poll_interval_default():
    """Test Settings has max_poll_interval_seconds with default of 30."""
    s = Settings()
    assert s.max_poll_interval_seconds == 30.0


def test_settings_max_poll_interval_custom():
    """Test Settings accepts custom max_poll_interval_seconds."""
    s = Settings(max_poll_interval_seconds=60.0)
    assert s.max_poll_interval_seconds == 60.0
