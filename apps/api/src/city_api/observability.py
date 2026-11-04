"""Ship structured JSON logs to Axiom without ever blocking or crashing the app.

This file is kept byte-identical in ``apps/api/src/city_api/observability.py`` and
``apps/worker/src/city_worker/observability.py`` (the two apps build separate Docker
images from their own directories, so they cannot share a package). It is stdlib-only
on purpose: no new runtime dependency for either app. ``tests/test_axiom_observability.py``
at the repo root enforces the two copies stay identical and tests them.

Load-bearing properties (ported from sarto-db ``api/observability.py``):

* **Routing fails to dev, never to production.** ``dataset_for_env`` sends exactly one
  ``APP_ENV`` value, ``production``, to the production dataset. Anything else, including
  unset or misspelled, goes to the dev dataset, and when no dev dataset is configured
  nothing ships at all (stdout only).
* **No request waits on Axiom.** Log calls only build a dict and put it on a bounded
  queue. A single daemon thread drains the queue in batches and does the HTTP.
* **Axiom being down never takes the app down.** Every shipping failure is counted and
  reported to stderr (rate-limited), never raised. A full queue drops records and counts
  the drop instead of blocking or growing without bound.
* **With AXIOM_* unset nothing changes.** ``configure_axiom_logging`` returns ``None``
  without touching any logger, so stdout logging is exactly what it was.
"""

from __future__ import annotations

import atexit
import contextvars
import json
import logging
import os
import queue
import re
import sys
import threading
import time
import traceback
import urllib.request
import uuid
from datetime import UTC, datetime
from typing import Any

PRODUCTION_ENV = "production"
# Production dataset. There is no default dev dataset: off production, logs only ship
# when AXIOM_DATASET_DEV is set explicitly, so a dev box can never write into prod.
DEFAULT_DATASET = "city-doodle"
AXIOM_INGEST_URL = "https://api.axiom.co/v1/datasets/{dataset}/ingest"

# Bounded so an Axiom outage costs a fixed amount of memory; past this, records are
# dropped and counted. Losing logs beats an OOM kill that loses the process.
QUEUE_MAX_RECORDS = 10_000
# The drain thread ships up to this many records per HTTP call, waiting at most
# FLUSH_INTERVAL_S for a batch to fill.
MAX_BATCH = 500
FLUSH_INTERVAL_S = 1.0
INGEST_TIMEOUT_S = 10.0
# The most stopping the drain thread may take at process exit.
SHUTDOWN_TIMEOUT_S = 3.0
# Shipping failures are reported to stderr at most this often, so an outage does not
# turn into a stderr line per batch.
FAILURE_REPORT_INTERVAL_S = 60.0

# An inbound X-Request-ID is caller-controlled and written into every line for the
# request, so it is only honoured when it is a short token.
REQUEST_ID_PATTERN = re.compile(r"[A-Za-z0-9._:-]{1,128}")

# Fields bound for the current request / job. Holds a dict that code further down the
# call stack may mutate (see ``set_log_fields``), so values set inside a dependency are
# visible to the middleware that logs the request line afterwards.
_log_context: contextvars.ContextVar[dict[str, Any] | None] = contextvars.ContextVar(
    "city_log_context", default=None
)

# LogRecord attributes that are not user-supplied ``extra=`` fields.
_RESERVED_ATTRS = frozenset(
    vars(logging.LogRecord("", 0, "", 0, "", (), None)).keys() | {"message", "asctime", "taskName"}
)


def dataset_for_env(
    app_env: str | None,
    *,
    production_dataset: str | None,
    dev_dataset: str | None,
) -> str | None:
    """The Axiom dataset an environment writes to.

    Only ``production`` (case/whitespace-insensitive) reaches ``production_dataset``.
    Everything else, including ``None`` and typos like ``prod``, goes to ``dev_dataset``
    (which may be ``None``, meaning "do not ship"): a lost dev log is noticed, a polluted
    production dataset is not.
    """
    if (app_env or "").strip().lower() == PRODUCTION_ENV:
        return production_dataset
    return dev_dataset


def request_id_from(header: str | None) -> str:
    """The caller's request id if it is a short token, else a fresh one."""
    if header and REQUEST_ID_PATTERN.fullmatch(header):
        return header
    return uuid.uuid4().hex


def bind_log_context(**fields: Any) -> contextvars.Token:
    """Start a fresh log context (per request / per job). Pass the token to ``reset_log_context``."""
    return _log_context.set({k: v for k, v in fields.items() if v is not None})


def reset_log_context(token: contextvars.Token) -> None:
    _log_context.reset(token)


def set_log_fields(**fields: Any) -> None:
    """Add fields to the current context, e.g. ``set_log_fields(user_id=...)`` once auth resolves.

    A no-op outside a bound context.
    """
    ctx = _log_context.get()
    if ctx is not None:
        ctx.update(fields)


def get_log_context() -> dict[str, Any]:
    return dict(_log_context.get() or {})


class JsonEventFormatter:
    """Turn a LogRecord into a flat, JSON-ready dict for Axiom.

    Runs on the logging thread (not the drain thread) because it reads the context var,
    which is per request / per task.
    """

    def __init__(self, static_fields: dict[str, Any]) -> None:
        self.static_fields = {k: v for k, v in static_fields.items() if v}

    def to_event(self, record: logging.LogRecord) -> dict[str, Any]:
        event: dict[str, Any] = {
            "_time": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname.lower(),
            "logger_name": record.name,
            "message": record.getMessage(),
        }
        event.update(self.static_fields)
        event.update(_log_context.get() or {})
        for key, value in record.__dict__.items():
            if key not in _RESERVED_ATTRS and not key.startswith("_"):
                event[key] = value
        if record.exc_info and record.exc_info[0] is not None:
            exc_type, exc_value, exc_tb = record.exc_info
            event["exc_type"] = exc_type.__name__
            event["exc_message"] = str(exc_value)
            event["exc_traceback"] = "".join(
                traceback.format_exception(exc_type, exc_value, exc_tb)
            )
        return event


class AxiomShipper:
    """Bounded queue + one daemon thread that POSTs batches to Axiom's ingest API."""

    _STOP = object()

    def __init__(
        self,
        token: str,
        dataset: str,
        org_id: str | None = None,
        *,
        url: str | None = None,
        timeout_s: float = INGEST_TIMEOUT_S,
        max_queue: int = QUEUE_MAX_RECORDS,
    ) -> None:
        self.token = token
        self.dataset = dataset
        self.org_id = org_id
        self.url = url or AXIOM_INGEST_URL.format(dataset=dataset)
        self.timeout_s = timeout_s
        self.queue: queue.Queue[Any] = queue.Queue(maxsize=max_queue)
        self._lock = threading.Lock()
        self.failed_records = 0
        self.dropped_records = 0
        self.last_failure: str | None = None
        self._last_report = 0.0
        self._thread: threading.Thread | None = None

    # -- producer side (any thread; must never block or raise) --------------------

    def submit(self, event: dict[str, Any]) -> None:
        try:
            self.queue.put_nowait(event)
        except queue.Full:
            with self._lock:
                self.dropped_records += 1

    # -- drain thread ------------------------------------------------------------

    def start(self) -> None:
        if self._thread is None:
            self._thread = threading.Thread(target=self._run, name="axiom-log-shipper", daemon=True)
            self._thread.start()

    def is_drain_thread(self) -> bool:
        return threading.current_thread() is self._thread

    def _run(self) -> None:
        while True:
            item = self.queue.get()
            if item is self._STOP:
                self.queue.task_done()
                return
            batch = [item]
            stop = False
            deadline = time.monotonic() + FLUSH_INTERVAL_S
            while len(batch) < MAX_BATCH:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                try:
                    nxt = self.queue.get(timeout=remaining)
                except queue.Empty:
                    break
                if nxt is self._STOP:
                    stop = True
                    self.queue.task_done()
                    break
                batch.append(nxt)
            self.ship(batch)
            for _ in batch:
                self.queue.task_done()
            if stop:
                return

    def ship(self, batch: list[dict[str, Any]]) -> bool:
        """POST one batch. Never raises; returns whether Axiom accepted it."""
        try:
            body = json.dumps(batch, default=str).encode("utf-8")
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            }
            if self.org_id:
                headers["X-Axiom-Org-Id"] = self.org_id
            req = urllib.request.Request(self.url, data=body, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                resp.read()
            return True
        except Exception as exc:  # noqa: BLE001 - Axiom being down must not break the app
            self._record_failure(len(batch), exc)
            return False

    def _record_failure(self, n: int, exc: BaseException) -> None:
        with self._lock:
            self.failed_records += n
            self.last_failure = f"{type(exc).__name__}: {exc}"
            now = time.monotonic()
            report = (
                now - self._last_report >= FAILURE_REPORT_INTERVAL_S or self._last_report == 0.0
            )
            if report:
                self._last_report = now
            failed, dropped = self.failed_records, self.dropped_records
        if report:
            try:
                print(
                    f"[axiom] failed to ship {n} log record(s) to {self.dataset}: "
                    f"{type(exc).__name__}: {exc} (failed so far: {failed}, dropped: {dropped})",
                    file=sys.stderr,
                    flush=True,
                )
            except Exception:  # noqa: BLE001 - stderr itself may be gone at exit
                pass

    # -- lifecycle ---------------------------------------------------------------

    def flush(self, timeout_s: float = 5.0) -> bool:
        """Wait until every queued record has been handled (shipped or failed)."""
        deadline = time.monotonic() + timeout_s
        with self.queue.all_tasks_done:
            while self.queue.unfinished_tasks:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self.queue.all_tasks_done.wait(remaining)
        return True

    def stop(self, timeout_s: float = SHUTDOWN_TIMEOUT_S) -> None:
        thread = self._thread
        if thread is None:
            return
        deadline = time.monotonic() + timeout_s
        try:
            self.queue.put(self._STOP, timeout=timeout_s)
        except queue.Full:
            print("[axiom] log queue still full at shutdown; abandoning it", file=sys.stderr)
        else:
            thread.join(timeout=max(0.0, deadline - time.monotonic()))
        self._thread = None


class AxiomHandler(logging.Handler):
    """Logging handler that formats on the caller's thread and enqueues for the shipper."""

    def __init__(
        self, shipper: AxiomShipper, formatter: JsonEventFormatter, level: int = 0
    ) -> None:
        super().__init__(level)
        self.shipper = shipper
        self.event_formatter = formatter

    def emit(self, record: logging.LogRecord) -> None:
        # Anything logged while shipping (e.g. by urllib) would loop back into the queue.
        if self.shipper.is_drain_thread():
            return
        try:
            self.shipper.submit(self.event_formatter.to_event(record))
        except Exception:  # noqa: BLE001 - logging must never raise into the app
            self.handleError(record)


_installed: list[tuple[logging.Logger, logging.Handler]] = []
_shipper: AxiomShipper | None = None


def configure_axiom_logging(
    *,
    service: str,
    app_env: str | None,
    api_token: str | None,
    org_id: str | None = None,
    dataset: str | None = DEFAULT_DATASET,
    dataset_dev: str | None = None,
    log_level: str = "info",
    extra_loggers: tuple[str, ...] = (),
    preserve_stderr_fallback: bool = False,
) -> str | None:
    """Attach the Axiom sink to the root logger if configured; return the dataset or ``None``.

    With no token, or no dataset for this env (off production with AXIOM_DATASET_DEV
    unset), this returns ``None`` and changes nothing.

    ``extra_loggers`` names non-propagating loggers (e.g. ``uvicorn``) that should also
    ship; the handler is only added to those that do not propagate to root, so nothing
    ships twice.

    ``preserve_stderr_fallback``: when the root logger has no handlers, Python prints
    WARNING+ records to stderr via ``logging.lastResort``. Adding our handler to root
    disables that, so this installs an equivalent stderr handler to keep stdout/stderr
    output unchanged (the API relies on this; the worker configures its own handler).
    """
    shutdown_axiom_logging()
    target = dataset_for_env(app_env, production_dataset=dataset, dev_dataset=dataset_dev)
    if not (api_token and target):
        return None

    global _shipper
    try:
        shipper = AxiomShipper(api_token, target, org_id)
        formatter = JsonEventFormatter(
            {
                "service": service,
                "app_env": (app_env or "").strip().lower() or "development",
                "fly_region": os.environ.get("FLY_REGION"),
                "fly_machine_id": os.environ.get("FLY_MACHINE_ID"),
                "fly_image_ref": os.environ.get("FLY_IMAGE_REF"),
            }
        )
        level = logging.getLevelName((log_level or "info").upper())
        if not isinstance(level, int):
            level = logging.INFO
        handler = AxiomHandler(shipper, formatter, level)

        root = logging.getLogger()
        if preserve_stderr_fallback and not root.handlers:
            fallback = logging.StreamHandler(sys.stderr)
            fallback.setLevel(logging.WARNING)
            root.addHandler(fallback)
            _installed.append((root, fallback))
        if root.level == logging.NOTSET or root.level > level:
            root.setLevel(level)
        root.addHandler(handler)
        _installed.append((root, handler))
        for name in extra_loggers:
            lg = logging.getLogger(name)
            if not lg.propagate:
                lg.addHandler(handler)
                _installed.append((lg, handler))

        shipper.start()
        _shipper = shipper
    except Exception as exc:  # noqa: BLE001 - observability setup must not stop startup
        print(f"[axiom] log shipping disabled, setup failed: {exc!r}", file=sys.stderr)
        shutdown_axiom_logging()
        return None
    return target


def shutdown_axiom_logging() -> None:
    """Flush briefly, stop the drain thread and detach only the handlers we installed."""
    global _shipper
    if _shipper is not None:
        _shipper.flush(SHUTDOWN_TIMEOUT_S)
        _shipper.stop()
        _shipper = None
    while _installed:
        lg, handler = _installed.pop()
        lg.removeHandler(handler)


def current_shipper() -> AxiomShipper | None:
    return _shipper


atexit.register(shutdown_axiom_logging)
