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
