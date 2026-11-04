"""CITY-642: request logging middleware fields and the AXIOM-unset no-op."""

import logging

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from city_api import observability
from city_api.request_logging import RequestLoggingMiddleware


class _Capture(logging.Handler):
    def __init__(self):
        super().__init__(logging.DEBUG)
        self.records: list[logging.LogRecord] = []

    def emit(self, record):
        self.records.append(record)


@pytest.fixture
def captured():
    lg = logging.getLogger("city_api.request")
    handler = _Capture()
    old_level = lg.level
    lg.addHandler(handler)
    lg.setLevel(logging.DEBUG)
    yield handler.records
    lg.removeHandler(handler)
    lg.setLevel(old_level)


def _request_lines(records):
    return [r for r in records if getattr(r, "event", None) == "request"]


def test_axiom_disabled_when_unconfigured():
    """With AXIOM_API_TOKEN unset (the test env), importing the app installs nothing."""
    assert observability.current_shipper() is None


@pytest.mark.asyncio
async def test_request_line_fields(client, captured):
    response = await client.get("/")
    assert response.status_code == 200
    (line,) = _request_lines(captured)
    assert line.levelno == logging.INFO
    assert line.method == "GET"
    assert line.route == "/"
    assert line.path == "/"
    assert line.status == 200
    assert isinstance(line.duration_ms, float) and line.duration_ms >= 0
    assert response.headers["x-request-id"]


@pytest.mark.asyncio
async def test_route_template_not_raw_path(client, captured):
    world_id = "00000000-0000-0000-0000-0000000000ff"
    response = await client.get(f"/worlds/{world_id}")
    (line,) = _request_lines(captured)
    assert line.route == "/worlds/{world_id}"
    assert line.path == f"/worlds/{world_id}"
    assert line.status == response.status_code


@pytest.mark.asyncio
async def test_inbound_request_id_is_honoured_and_echoed(client, captured):
    response = await client.get("/", headers={"X-Request-ID": "trace-abc.123"})
    assert response.headers["x-request-id"] == "trace-abc.123"
    assert observability.get_log_context() == {}
    # The middleware binds request_id in the log context, not on the record itself.
    (line,) = _request_lines(captured)
    assert line.status == 200


@pytest.mark.asyncio
async def test_hostile_request_id_is_replaced(client):
    response = await client.get("/", headers={"X-Request-ID": "x" * 500})
    assert response.headers["x-request-id"] != "x" * 500
    assert len(response.headers["x-request-id"]) == 32


@pytest.mark.asyncio
async def test_health_logged_at_debug(client, captured):
    await client.get("/health")
    (line,) = _request_lines(captured)
    assert line.levelno == logging.DEBUG


def _mini_app():
    app = FastAPI()
    app.add_middleware(RequestLoggingMiddleware)

    @app.get("/items/{item_id}")
    async def item(item_id: str):
        # What an auth dependency would do once it has resolved the user.
        observability.set_log_fields(user_id="user-42")
        seen.update(observability.get_log_context())
        return {"ok": True}

    @app.get("/boom")
    async def boom():
        raise RuntimeError("kaboom")

    seen: dict = {}
    return app, seen


@pytest.mark.asyncio
async def test_context_carries_request_id_and_user_id(captured):
    app, seen = _mini_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        response = await c.get("/items/7", headers={"X-Request-ID": "rid-7"})
    assert seen["request_id"] == "rid-7"
    (line,) = _request_lines(captured)
    assert line.route == "/items/{item_id}"
    assert line.user_id == "user-42"
    assert response.headers["x-request-id"] == "rid-7"


@pytest.mark.asyncio
async def test_unhandled_exception_logged_as_500_with_exc_info(captured):
    app, _ = _mini_app()
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        response = await c.get("/boom")
    assert response.status_code == 500
    (line,) = _request_lines(captured)
    assert line.status == 500
    assert line.route == "/boom"
    assert line.exc_info[0] is RuntimeError


@pytest.mark.asyncio
async def test_request_line_ships_with_request_id_in_axiom_event(captured):
    """End to end through the Axiom formatter: request_id comes from the bound context."""
    events = []

    class FakeShipper:
        def submit(self, event):
            events.append(event)

        def is_drain_thread(self):
            return False

    handler = observability.AxiomHandler(
        FakeShipper(), observability.JsonEventFormatter({"service": "api"})
    )
    lg = logging.getLogger("city_api.request")
    lg.addHandler(handler)
    try:
        app, _ = _mini_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            await c.get("/items/9", headers={"X-Request-ID": "rid-9"})
    finally:
        lg.removeHandler(handler)
    (event,) = [e for e in events if e.get("event") == "request"]
    assert event["request_id"] == "rid-9"
    assert event["user_id"] == "user-42"
    assert event["route"] == "/items/{item_id}"
    assert event["status"] == 200
    assert event["service"] == "api"
