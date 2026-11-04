"""CITY-642: request logging middleware fields and the AXIOM-unset no-op."""

import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from city_api import observability
from city_api.request_logging import RequestLoggingMiddleware
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient


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
        def submit(self, encoded):
            events.append(json.loads(encoded))

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


# --- CITY-642 review: no secrets / PII reach Axiom ----------------------------------
# Each test ships through the real handler + shipper to a local HTTP collector and
# asserts on the bytes Axiom would have received.

EMAIL = "alice@example.com"
SESSION_TOKEN = "sess_9f8e7d6c5b4a"
QUERY_SECRET = "qs-secret-42"


@pytest.fixture
def shipped():
    """Root logger -> AxiomHandler -> AxiomShipper -> local collector. Yields a reader."""
    bodies: list[bytes] = []

    class Collector(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802 - http.server API
            bodies.append(self.rfile.read(int(self.headers["Content-Length"])))
            self.send_response(200)
            self.end_headers()

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Collector)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    shipper = observability.AxiomShipper(
        "xaat-test", "ds", url=f"http://127.0.0.1:{server.server_port}/ingest"
    )
    shipper.start()
    handler = observability.AxiomHandler(
        shipper, observability.JsonEventFormatter({"service": "api"}), logging.INFO
    )
    root = logging.getLogger()
    old_level = root.level
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    # As configure_axiom_logging does: the test's own httpx client logs full URLs.
    httpx_logger = logging.getLogger("httpx")
    old_httpx = httpx_logger.level
    httpx_logger.setLevel(logging.WARNING)

    def read() -> tuple[str, list[dict]]:
        assert shipper.flush(5)
        events = [e for body in bodies for e in json.loads(body)]
        return b"".join(bodies).decode(), events

    yield read
    root.removeHandler(handler)
    root.setLevel(old_level)
    httpx_logger.setLevel(old_httpx)
    shipper.stop(1)
    server.shutdown()
    server.server_close()


def _asyncpg_unique_violation():
    """The exception SQLAlchemy raises for a duplicate email on asyncpg."""
    import asyncpg
    from sqlalchemy.dialects.postgresql.asyncpg import AsyncAdapt_asyncpg_dbapi
    from sqlalchemy.exc import IntegrityError

    driver = asyncpg.exceptions.UniqueViolationError(
        'duplicate key value violates unique constraint "users_email_key"'
    )
    driver.detail = f"Key (email)=({EMAIL}) already exists."
    driver.constraint_name = "users_email_key"
    driver.table_name = "users"
    adapted = AsyncAdapt_asyncpg_dbapi.IntegrityError(f"{type(driver)}: {driver}", driver)
    adapted.__cause__ = driver
    exc = IntegrityError(
        "INSERT INTO users (email, password_hash) VALUES ($1, $2)",
        (EMAIL, "hash"),
        adapted,
    )
    assert EMAIL in str(exc) and EMAIL in str(exc.orig)  # the leak being guarded
    return exc


def _request(path="/auth/register", query=f"token={QUERY_SECRET}"):
    from fastapi import Request

    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": path,
            "query_string": query.encode(),
            "headers": [(b"host", b"testserver")],
            "server": ("testserver", 80),
            "scheme": "http",
        }
    )


@pytest.mark.asyncio
async def test_duplicate_email_never_ships(shipped):
    from city_api.main import integrity_error_handler

    exc = _asyncpg_unique_violation()
    response = await integrity_error_handler(_request(), exc)
    assert response.status_code == 409
    raw, events = shipped()
    assert EMAIL not in raw and QUERY_SECRET not in raw
    (event,) = [e for e in events if "integrity error" in e["message"]]
    assert "/auth/register" in event["message"]
    assert "UniqueViolationError" in event["message"]
    assert "constraint=users_email_key" in event["message"]


@pytest.mark.asyncio
async def test_session_token_in_sql_parameters_never_ships(shipped):
    """Even without hide_parameters, the parameters and DETAIL are scrubbed centrally."""
    from city_api.main import dbapi_error_handler
    from sqlalchemy.exc import DBAPIError

    orig = Exception(f"connection reset\nDETAIL:  Key (token)=({SESSION_TOKEN}) is not present.")
    exc = DBAPIError.instance(
        "SELECT * FROM sessions WHERE sessions.token = $1",
        (SESSION_TOKEN,),
        orig,
        Exception,
        hide_parameters=False,
    )
    assert SESSION_TOKEN in str(exc)
    try:
        raise exc
    except DBAPIError:
        response = await dbapi_error_handler(_request("/auth/me"), exc)
        # A library logging the raw exception with a traceback is scrubbed too.
        logging.getLogger("some.library").exception("db failed: %s", exc)
    assert response.status_code == 503
    raw, _ = shipped()
    assert SESSION_TOKEN not in raw and QUERY_SECRET not in raw
    assert "[parameters: redacted]" in raw


@pytest.mark.asyncio
async def test_query_string_never_ships_from_real_requests(client, shipped):
    await client.get(f"/?token={QUERY_SECRET}")
    await client.get(f"/does-not-exist?session={QUERY_SECRET}")
    raw, events = shipped()
    assert QUERY_SECRET not in raw
    paths = {e.get("path") for e in events if e.get("event") == "request"}
    assert {"/", "/does-not-exist"} <= paths


@pytest.mark.asyncio
async def test_unhandled_db_error_on_request_line_is_redacted(shipped):
    from fastapi import FastAPI

    app = FastAPI()
    app.add_middleware(RequestLoggingMiddleware)

    @app.post("/register")
    async def register():
        raise _asyncpg_unique_violation()

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        response = await c.post(f"/register?token={QUERY_SECRET}")
    assert response.status_code == 500
    raw, events = shipped()
    assert EMAIL not in raw and QUERY_SECRET not in raw
    (line,) = [e for e in events if e.get("event") == "request"]
    assert line["exc_type"] == "IntegrityError"
    assert "DETAIL: [redacted]" in line["exc_traceback"]


UUID_SECRET = "tok-SECRETSESSION-123"


def _asyncpg_uuid_bind_error():
    """What SQLAlchemy raises when a str that isn't a UUID is bound to a UUID param.

    Built the way asyncpg builds it: pgproto's UUID codec raises
    `ValueError: invalid UUID '<value>': ...`, and asyncpg chains that under
    `DataError: invalid input for query argument $1: '<value>' (...)`. SQLAlchemy's
    hide_parameters hides `[parameters]` but not these chained messages (CITY-686).
    """
    import asyncpg
    from asyncpg.pgproto.pgproto import UUID
    from sqlalchemy.dialects.postgresql.asyncpg import AsyncAdapt_asyncpg_dbapi
    from sqlalchemy.exc import DBAPIError

    try:
        try:
            UUID(UUID_SECRET)
        except ValueError as codec_error:
            raise asyncpg.exceptions.DataError(
                f"invalid input for query argument $1: {UUID_SECRET!r} ({codec_error})"
            ) from codec_error
    except asyncpg.exceptions.DataError as driver:
        try:
            raise AsyncAdapt_asyncpg_dbapi.Error(str(driver)) from driver
        except AsyncAdapt_asyncpg_dbapi.Error as adapted:
            exc = DBAPIError.instance(
                "SELECT * FROM sessions WHERE sessions.user_id = $1::UUID",
                (UUID_SECRET,),
                adapted,
                AsyncAdapt_asyncpg_dbapi.Error,
                hide_parameters=True,
            )
            exc.__cause__ = adapted
    tb = "".join(__import__("traceback").format_exception(exc))
    assert f"invalid UUID {UUID_SECRET!r}" in tb  # the leak being guarded
    return exc


@pytest.mark.asyncio
async def test_asyncpg_uuid_bind_value_never_ships(shipped):
    """CITY-686: the chained `invalid UUID '<value>'` line is redacted from tracebacks."""
    from city_api.main import dbapi_error_handler
    from sqlalchemy.exc import DBAPIError

    exc = _asyncpg_uuid_bind_error()
    try:
        raise exc
    except DBAPIError:
        response = await dbapi_error_handler(_request("/worlds"), exc)
        logging.getLogger("some.library").exception("lookup failed")
    assert response.status_code == 503

    app = FastAPI()
    app.add_middleware(RequestLoggingMiddleware)

    @app.get("/worlds")
    async def worlds():
        raise _asyncpg_uuid_bind_error()

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        assert (await c.get("/worlds")).status_code == 500

    raw, events = shipped()
    assert UUID_SECRET not in raw
    tracebacks = [e["exc_traceback"] for e in events if e.get("exc_traceback")]
    assert len(tracebacks) == 2
    for tb in tracebacks:
        assert "ValueError: invalid UUID [redacted]" in tb
        assert "invalid input for query argument $1: [redacted]" in tb


def test_api_engine_hides_sql_parameters():
    from city_api.database import get_engine

    assert get_engine().sync_engine.hide_parameters is True


def test_cors_exposes_request_id_header():
    from city_api.main import app
    from starlette.middleware.cors import CORSMiddleware

    (cors,) = [m for m in app.user_middleware if m.cls is CORSMiddleware]
    assert "X-Request-ID" in cors.kwargs["expose_headers"]
