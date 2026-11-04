"""CITY-642: worker job lifecycle log events carry job/world context."""

import json
import logging
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from city_worker import observability
from city_worker.models import JobType
from city_worker.runner import JobRunner


@pytest.fixture
def events():
    collected: list[dict] = []

    class FakeShipper:
        def submit(self, encoded):
            collected.append(json.loads(encoded))

        def is_drain_thread(self):
            return False

    handler = observability.AxiomHandler(
        FakeShipper(), observability.JsonEventFormatter({"service": "worker"})
    )
    lg = logging.getLogger("city_worker")
    old_level = lg.level
    lg.addHandler(handler)
    lg.setLevel(logging.INFO)
    yield collected
    lg.removeHandler(handler)
    lg.setLevel(old_level)


def _by_event(events, name):
    return [e for e in events if e.get("event") == name]


@pytest.mark.asyncio
async def test_successful_job_lifecycle(events):
    runner = JobRunner()
    job_id = uuid4()
    world_id = str(uuid4())

    async def handler(job_id_arg, job_type, params):
        logging.getLogger("city_worker.terrain").info("inside the handler")
        return {"ok": True}

    with (
        patch.object(runner, "_run_job_handler", side_effect=handler),
        patch.object(runner, "_update_job_status", new_callable=AsyncMock),
    ):
        await runner._execute_job(job_id, JobType.TERRAIN_GENERATION.value, {"world_id": world_id})

    (started,) = _by_event(events, "job_started")
    (finished,) = _by_event(events, "job_finished")
    (inner,) = [e for e in events if e["message"] == "inside the handler"]
    for e in (started, finished, inner):
        assert e["job_id"] == str(job_id)
        assert e["job_type"] == "terrain_generation"
        assert e["world_id"] == world_id
        assert e["service"] == "worker"
    assert finished["outcome"] == "completed"
    assert finished["duration_ms"] >= 0
    # Context is cleared once the job ends.
    assert observability.get_log_context() == {}


@pytest.mark.asyncio
async def test_failed_job_logs_error_outcome_and_exception(events):
    runner = JobRunner()
    job_id = uuid4()

    with (
        patch.object(runner, "_run_job_handler", side_effect=RuntimeError("coast exploded")),
        patch.object(runner, "_update_job_status", new_callable=AsyncMock),
        patch.object(runner, "_get_retry_info", new=AsyncMock(return_value=(3, 3))),
    ):
        await runner._execute_job(job_id, JobType.CITY_GROWTH.value, {})

    (finished,) = _by_event(events, "job_finished")
    assert finished["outcome"] == "error"
    assert finished["level"] == "error"
    assert finished["exc_type"] == "RuntimeError"
    assert finished["exc_message"] == "coast exploded"
    assert "world_id" not in finished
    (permanent,) = _by_event(events, "job_failed_permanently")
    assert permanent["job_id"] == str(job_id)
    assert permanent["retry_count"] == 3


@pytest.mark.asyncio
async def test_retry_scheduled_event(events):
    runner = JobRunner()
    job_id = uuid4()

    with (
        patch.object(runner, "_run_job_handler", side_effect=RuntimeError("flaky")),
        patch.object(runner, "_get_retry_info", new=AsyncMock(return_value=(0, 3))),
        patch("city_worker.runner.get_session", new=AsyncMock(side_effect=RuntimeError("no db"))),
    ):
        with pytest.raises(RuntimeError, match="no db"):
            await runner._execute_job(job_id, JobType.EXPORT_PNG.value, {})

    (retry,) = _by_event(events, "job_retry_scheduled")
    assert retry["job_id"] == str(job_id)
    assert retry["retry_count"] == 1
    assert retry["retry_delay_s"] == 30
    assert observability.get_log_context() == {}


def test_worker_engine_hides_sql_parameters():
    """CITY-642 review: bound SQL parameters must not reach logs (or Axiom)."""
    from city_worker.database import engine

    assert engine.sync_engine.hide_parameters is True


@pytest.mark.asyncio
async def test_job_failure_with_db_detail_is_redacted(events):
    """CITY-642 review: the worker's logger.exception ships no DB row values."""
    runner = JobRunner()
    err = RuntimeError(
        'duplicate key value violates unique constraint "tiles_pkey"\n'
        "DETAIL:  Key (world_id, tx, ty)=(secret-world, 1, 2) already exists."
    )
    with (
        patch.object(runner, "_run_job_handler", side_effect=err),
        patch.object(runner, "_update_job_status", new_callable=AsyncMock),
        patch.object(runner, "_get_retry_info", new=AsyncMock(return_value=(3, 3))),
    ):
        await runner._execute_job(uuid4(), JobType.TERRAIN_GENERATION.value, {})
    (finished,) = _by_event(events, "job_finished")
    assert "secret-world" not in json.dumps(finished)
    assert "DETAIL: [redacted]" in finished["exc_message"]
