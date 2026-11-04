"""Tests for the API/worker Axiom log shipper (CITY-642).

``observability.py`` is stdlib-only and duplicated byte-for-byte in apps/api and
apps/worker (each app builds its own Docker image). It is tested here, at the repo
root, because this is the suite CI runs, and loading it by file path needs neither
app's dependencies.
"""

from __future__ import annotations

import importlib.util
import json
import logging
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
API_COPY = ROOT / "apps/api/src/city_api/observability.py"
WORKER_COPY = ROOT / "apps/worker/src/city_worker/observability.py"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


obs = _load(API_COPY, "_city_observability_under_test")


def test_api_and_worker_copies_are_identical():
    assert API_COPY.read_bytes() == WORKER_COPY.read_bytes(), (
        "apps/api/src/city_api/observability.py and apps/worker/src/city_worker/"
        "observability.py must stay identical; copy one over the other."
    )


# --- dataset routing -------------------------------------------------------------


@pytest.mark.parametrize("app_env", ["production", "Production", " PRODUCTION "])
def test_only_production_routes_to_production_dataset(app_env):
    assert obs.dataset_for_env(app_env, production_dataset="prod", dev_dataset="dev") == "prod"


@pytest.mark.parametrize(
    "app_env", [None, "", "development", "staging", "prod", "production-ish", "test"]
)
def test_everything_else_routes_to_dev_dataset(app_env):
    assert obs.dataset_for_env(app_env, production_dataset="prod", dev_dataset="dev") == "dev"


@pytest.mark.parametrize("app_env", [None, "development", "prod"])
def test_non_production_without_dev_dataset_ships_nowhere(app_env):
    assert obs.dataset_for_env(app_env, production_dataset="prod", dev_dataset=None) is None


# --- configure: unset means unchanged --------------------------------------------


@pytest.fixture
def clean_root():
    root = logging.getLogger()
    handlers, level = list(root.handlers), root.level
    yield root
    obs.shutdown_axiom_logging()
    root.handlers[:] = handlers
    root.setLevel(level)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"app_env": "production", "api_token": None},
        {"app_env": "production", "api_token": ""},
        # A token on a dev box with no dev dataset must not write into production.
        {"app_env": "development", "api_token": "xaat-test"},
        {"app_env": None, "api_token": "xaat-test", "dataset_dev": ""},
    ],
)
def test_configure_is_a_noop_when_not_configured(clean_root, kwargs):
    handlers, level = list(clean_root.handlers), clean_root.level
    assert obs.configure_axiom_logging(service="api", **kwargs) is None
    assert clean_root.handlers == handlers
    assert clean_root.level == level
    assert obs.current_shipper() is None


def test_configure_routes_production_and_detaches_cleanly(clean_root):
    before = list(clean_root.handlers)
    dataset = obs.configure_axiom_logging(
        service="api", app_env="production", api_token="xaat-test", dataset="city-doodle"
    )
    assert dataset == "city-doodle"
    assert obs.current_shipper().url.endswith("/v1/datasets/city-doodle/ingest")
    added = [h for h in clean_root.handlers if h not in before]
    assert any(isinstance(h, obs.AxiomHandler) for h in added)
    obs.shutdown_axiom_logging()
    assert clean_root.handlers == before


def test_configure_dev_env_uses_dev_dataset(clean_root):
    dataset = obs.configure_axiom_logging(
        service="worker",
        app_env="development",
        api_token="xaat-test",
        dataset="city-doodle",
        dataset_dev="city-doodle-dev",
    )
    assert dataset == "city-doodle-dev"


def test_stderr_fallback_preserved_when_root_had_no_handlers(clean_root):
    clean_root.handlers[:] = []
    obs.configure_axiom_logging(
        service="api",
        app_env="production",
        api_token="xaat-test",
        preserve_stderr_fallback=True,
    )
    streams = [
        h
        for h in clean_root.handlers
        if type(h) is logging.StreamHandler and h.stream is sys.stderr
    ]
    assert len(streams) == 1 and streams[0].level == logging.WARNING


# --- shipping --------------------------------------------------------------------


class _Collector(BaseHTTPRequestHandler):
    status = 200
    received: list = []

    def do_POST(self):  # noqa: N802 - http.server API
        length = int(self.headers["Content-Length"])
        type(self).received.append(
            {
                "path": self.path,
                "auth": self.headers.get("Authorization"),
                "body": json.loads(self.rfile.read(length)),
            }
        )
        self.send_response(type(self).status)
        self.end_headers()

    def log_message(self, *args):
        pass


@pytest.fixture
def collector():
    handler = type("Collector", (_Collector,), {"received": [], "status": 200})
    server = HTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield handler, f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()


def _logger_with(handler: logging.Handler, name: str) -> logging.Logger:
    lg = logging.getLogger(name)
    lg.handlers[:] = [handler]
    lg.propagate = False
    lg.setLevel(logging.DEBUG)
    return lg


def test_records_ship_as_flat_json_with_context(collector):
    handler_cls, base = collector
    shipper = obs.AxiomShipper("xaat-test", "ds", url=f"{base}/v1/datasets/ds/ingest")
    shipper.start()
    fmt = obs.JsonEventFormatter({"service": "api", "app_env": "production", "empty": None})
    lg = _logger_with(obs.AxiomHandler(shipper, fmt), "test.ship")

    token = obs.bind_log_context(request_id="rid-1", world_id=None)
    obs.set_log_fields(user_id="u-1")
    try:
        lg.info("hello %s", "world", extra={"event": "request", "status": 201})
        try:
            raise ValueError("boom")
        except ValueError:
            lg.exception("failed")
    finally:
        obs.reset_log_context(token)
    lg.info("after")

    assert shipper.flush(5)
    shipper.stop()
    events = [e for req in handler_cls.received for e in req["body"]]
    assert handler_cls.received[0]["auth"] == "Bearer xaat-test"
    assert handler_cls.received[0]["path"] == "/v1/datasets/ds/ingest"
    first, second, third = events
    assert first["message"] == "hello world"
    assert first["level"] == "info"
    assert first["logger_name"] == "test.ship"
    assert first["service"] == "api" and first["app_env"] == "production"
    assert "empty" not in first and "world_id" not in first
    assert first["request_id"] == "rid-1" and first["user_id"] == "u-1"
    assert first["event"] == "request" and first["status"] == 201
    assert first["_time"].endswith("+00:00")
    assert second["level"] == "error"
    assert second["exc_type"] == "ValueError" and second["exc_message"] == "boom"
    assert "Traceback" in second["exc_traceback"]
    assert "request_id" not in third
    assert shipper.failed_records == 0


def test_ingest_http_error_is_counted_not_raised(collector, capsys):
    handler_cls, base = collector
    handler_cls.status = 500
    shipper = obs.AxiomShipper("xaat-test", "ds", url=f"{base}/ingest")
    assert shipper.ship([{"message": "x"}, {"message": "y"}]) is False
    assert shipper.failed_records == 2
    assert "HTTPError" in shipper.last_failure
    assert "failed to ship 2 log record(s)" in capsys.readouterr().err


def test_unreachable_axiom_never_raises_into_logging_calls(capsys):
    # Nothing listens on port 9 here; connection refused, on the drain thread.
    shipper = obs.AxiomShipper("xaat-test", "ds", url="http://127.0.0.1:9/ingest", timeout_s=2)
    shipper.start()
    lg = _logger_with(obs.AxiomHandler(shipper, obs.JsonEventFormatter({})), "test.down")
    for i in range(5):
        lg.error("still serving %d", i)  # must not raise or block
    assert shipper.flush(10)
    shipper.stop()
    assert shipper.failed_records == 5
    # Rate-limited: one stderr report for the outage, not one per batch.
    assert capsys.readouterr().err.count("[axiom] failed to ship") == 1


def test_full_queue_drops_and_counts_instead_of_blocking():
    shipper = obs.AxiomShipper("xaat-test", "ds", url="http://127.0.0.1:9/", max_queue=2)
    # Drain thread not started, so the queue fills.
    for i in range(5):
        shipper.submit({"n": i})
    assert shipper.dropped_records == 3


def test_handler_swallows_formatter_errors(capsys):
    class Broken(obs.JsonEventFormatter):
        def to_event(self, record):
            raise RuntimeError("bad formatter")

    shipper = obs.AxiomShipper("xaat-test", "ds", url="http://127.0.0.1:9/")
    handler = obs.AxiomHandler(shipper, Broken({}))
    lg = _logger_with(handler, "test.broken")
    lg.info("x")  # handleError prints to stderr, never raises
    assert shipper.queue.qsize() == 0


def test_records_logged_on_the_drain_thread_are_not_requeued():
    shipper = obs.AxiomShipper("xaat-test", "ds", url="http://127.0.0.1:9/")
    handler = obs.AxiomHandler(shipper, obs.JsonEventFormatter({}))
    record = logging.LogRecord("urllib3", logging.WARNING, "", 0, "retrying", (), None)
    shipper._thread = threading.current_thread()
    handler.emit(record)
    assert shipper.queue.qsize() == 0


@pytest.mark.parametrize(
    "header,kept",
    [("abc-123", True), ("a" * 128, True), ("a" * 129, False), ("x y", False), (None, False)],
)
def test_request_id_from(header, kept):
    rid = obs.request_id_from(header)
    assert (rid == header) is kept
    assert obs.REQUEST_ID_PATTERN.fullmatch(rid)


# --- review fixups: per-record encoding, drop reports, shutdown budget, httpx -------


class _Unprintable:
    def __str__(self):
        raise RuntimeError("no str for you")

    __repr__ = __str__


def test_one_unserialisable_record_does_not_drop_its_batch(collector, capsys):
    handler_cls, base = collector
    shipper = obs.AxiomShipper("xaat-test", "ds", url=f"{base}/ingest")
    batch = [{"n": 1}, {"n": 2, "bad": _Unprintable()}, {"n": 3}]
    assert shipper.ship(batch) is True
    (request,) = handler_cls.received
    assert [e["n"] for e in request["body"]] == [1, 3]
    assert shipper.failed_records == 1
    assert "failed to ship 1 log record(s)" in capsys.readouterr().err


def test_queue_full_drops_are_reported_while_healthy(capsys):
    shipper = obs.AxiomShipper("xaat-test", "ds", url="http://127.0.0.1:9/", max_queue=1)
    for i in range(3):
        shipper.submit({"n": i})
    shipper._maybe_report_drops()
    assert "dropped 2 record(s)" in capsys.readouterr().err
    # Rate-limited: more drops right away are counted but not re-reported yet.
    shipper.submit({"n": 4})
    shipper._maybe_report_drops()
    assert capsys.readouterr().err == ""
    assert shipper.dropped_records == 3


def test_drain_thread_reports_drops_after_a_successful_batch(collector, capsys):
    handler_cls, base = collector
    shipper = obs.AxiomShipper("xaat-test", "ds", url=f"{base}/ingest", max_queue=1)
    for i in range(4):
        shipper.submit({"n": i})  # 1 queued, 3 dropped before the thread starts
    shipper.start()
    assert shipper.flush(5)
    shipper.stop()
    assert len(handler_cls.received) == 1 and shipper.failed_records == 0
    assert "dropped 3 record(s)" in capsys.readouterr().err


@pytest.fixture
def hanging_axiom():
    import time as _time
    from http.server import ThreadingHTTPServer

    class Hang(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802 - http.server API
            _time.sleep(8)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Hang)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()


def test_shutdown_with_hung_axiom_stays_within_one_budget(clean_root, hanging_axiom, monkeypatch):
    import time as _time

    monkeypatch.setattr(obs, "AXIOM_INGEST_URL", hanging_axiom + "/{dataset}/ingest")
    assert obs.configure_axiom_logging(service="api", app_env="production", api_token="xaat-t")
    logging.getLogger("test.hang").warning("this ingest will hang")
    _time.sleep(0.2)  # let the drain thread pick it up and block on the POST
    logging.getLogger("test.hang").warning("and this one waits behind it")
    start = _time.monotonic()
    obs.shutdown_axiom_logging()
    elapsed = _time.monotonic() - start
    assert elapsed < obs.SHUTDOWN_TIMEOUT_S + 0.5, elapsed
    assert obs.current_shipper() is None


def test_configure_holds_httpx_at_warning(clean_root):
    for name in ("httpx", "httpcore"):
        logging.getLogger(name).setLevel(logging.NOTSET)
    obs.configure_axiom_logging(service="api", app_env="production", api_token="xaat-t")
    assert logging.getLogger("httpx").level == logging.WARNING
    assert logging.getLogger("httpcore").level == logging.WARNING


# --- review round 2: central redaction, encode at log time -------------------------


@pytest.mark.parametrize(
    "text,secret",
    [
        (
            'duplicate key value violates unique constraint "users_email_key"\n'
            "DETAIL:  Key (email)=(alice@example.com) already exists.",
            "alice@example.com",
        ),
        ("[SQL: SELECT 1 WHERE token = $1]\n[parameters: ('sess_abc',)]", "sess_abc"),
        ("invalid input for query argument $1: 'sess_abc' (expected uuid)", "sess_abc"),
        # CITY-686: the chained asyncpg codec error quotes the value again.
        (
            "ValueError: invalid UUID 'sess_abc': length must be between 32..36 characters",
            "sess_abc",
        ),
        ('invalid input syntax for type uuid: "sess_abc"', "sess_abc"),
        ('invalid input value for enum cityclassification: "sess_abc"', "sess_abc"),
        ('value "4242424242" is out of range for type integer', "4242424242"),
        ("Key (owner_id)=(user-7) is not present in table users", "user-7"),
        (
            "1 validation error\n  [type=string_type, input_value='bob@x.io', input_type=str]",
            "bob@x.io",
        ),
    ],
)
def test_redact_sensitive_scrubs_db_values(text, secret):
    out = obs.redact_sensitive(text)
    assert secret not in out
    assert out.splitlines()[0].split()[0] == text.splitlines()[0].split()[0]


def test_formatter_redacts_message_exception_and_traceback():
    fmt = obs.JsonEventFormatter({})
    try:
        raise ValueError("boom\nDETAIL:  Key (email)=(a@b.c) already exists.")
    except ValueError:
        record = logging.LogRecord(
            "x", logging.ERROR, "", 0, "failed: %s", ("[parameters: ('tok',)]",), sys.exc_info()
        )
    event = fmt.to_event(record)
    blob = json.dumps(event)
    assert "a@b.c" not in blob and "'tok'" not in blob
    assert event["exc_type"] == "ValueError"


def test_handler_encodes_at_log_time_and_isolates_bad_records():
    shipper = obs.AxiomShipper("xaat-test", "ds", url="http://127.0.0.1:9/")
    lg = _logger_with(obs.AxiomHandler(shipper, obs.JsonEventFormatter({})), "test.encode")
    payload = {"step": "before"}
    lg.info("one", extra={"payload": payload})
    payload["step"] = "after"  # mutation after logging must not change what ships
    lg.info("two", extra={"bad": _Unprintable()})
    lg.info("three")
    queued = [shipper.queue.get_nowait() for _ in range(shipper.queue.qsize())]
    assert all(isinstance(q, str) for q in queued)
    events = [json.loads(q) for q in queued]
    assert [e["message"] for e in events] == ["one", "three"]
    assert events[0]["payload"] == {"step": "before"}
    assert shipper.failed_records == 1
