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
* **No row values or query parameters ship.** Messages, exception text and
  tracebacks pass through ``redact_sensitive`` (Postgres DETAIL lines, SQLAlchemy
  ``[parameters: ...]``, asyncpg argument errors, pydantic ``input_value``).
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
# Total time process exit may spend flushing and stopping the drain thread, shared by
# both steps. Fly's default kill_timeout is 5 s; past this the remaining records are
# abandoned rather than having the machine SIGKILLed mid-exit.
SHUTDOWN_TIMEOUT_S = 3.0
# Shipping failures and queue-full drops are each reported to stderr at most this
# often, so an outage or a burst does not turn into a stderr line per batch.
FAILURE_REPORT_INTERVAL_S = 60.0

# An inbound X-Request-ID is caller-controlled and written into every line for the
# request, so it is only honoured when it is a short token.
REQUEST_ID_PATTERN = re.compile(r"[A-Za-z0-9._:-]{1,128}")

# Database errors echo row values and query arguments into their text: Postgres puts
# `Key (email)=(alice@example.com) already exists.` in a DETAIL line that asyncpg
# includes in str(exc), SQLAlchemy appends `[parameters: (...)]` (unless the engine
# sets hide_parameters), and asyncpg says `invalid input for query argument $1: <value>`.
# Every shipped message/exception/traceback passes through ``redact_sensitive`` so none
# of that (emails, session tokens) lands in a durable, queryable store.
_REDACTIONS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"^([ \t]*)DETAIL:.*$", re.MULTILINE), r"\1DETAIL: [redacted]"),
    (re.compile(r"\[parameters: [^\n]*"), "[parameters: redacted]"),
    (re.compile(r"(invalid input for query argument \$\d+:)[^\n]*"), r"\1 [redacted]"),
    # CITY-686: asyncpg's codec errors are chained under that DataError and quote the
    # value again, e.g. `ValueError: invalid UUID 'tok-...': length must be ...`. The
    # value is always a repr (quoted), so only the quoted part is replaced and the rest
    # of the line survives.
    (
        re.compile(r"""(invalid UUID )b?(?:'(?:[^'\\\n]|\\.)*'|"(?:[^"\\\n]|\\.)*")"""),
        r"\1[redacted]",
    ),
    # Postgres data exceptions (SQLSTATE class 22) raised server-side echo the value.
    # Each message ends with the value, so everything after the anchored prefix goes:
    # `invalid input syntax for type uuid: "tok-..."`, `invalid input value for enum
    # x: "..."`, `malformed array literal: "..."`, `date/time field value out of
    # range: "..."`.
    (
        re.compile(
            r"((?:invalid input (?:syntax|value) for (?:type|enum) [^:\n]*"
            r"|malformed \w+ literal|date/time field value out of range):)[^\n]*"
        ),
        r"\1 [redacted]",
    ),
    # ...and these quote it mid-message: `value "..." is out of range for type integer`,
    # `invalid value "SECR" for "YYYY"` (to_date / to_timestamp).
    (
        re.compile(r'(\b(?:invalid )?value )"[^\n]*?"( is out of range for type| for ")'),
        r"\1[redacted]\2",
    ),
    # pydantic ValidationError text echoes the offending input.
    (re.compile(r"input_value=.*?, input_type="), "input_value=[redacted], input_type="),
    (
        re.compile(r"Key \(([^)\n]*)\)=\([^\n]*?\)( already exists| is not present)"),
        r"Key (\1)=([redacted])\2",
    ),
)


def redact_sensitive(text: object) -> str:
    """Scrub DB row values / query parameters from an error message or traceback."""
    out = str(text)
    for pattern, replacement in _REDACTIONS:
        out = pattern.sub(replacement, out)
    return out


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
    """Start a fresh log context (per request / job); pass the token to ``reset_log_context``."""
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
            "message": redact_sensitive(record.getMessage()),
        }
        event.update(self.static_fields)
        event.update(_log_context.get() or {})
        for key, value in record.__dict__.items():
            if key not in _RESERVED_ATTRS and not key.startswith("_"):
                event[key] = value
        if record.exc_info and record.exc_info[0] is not None:
            exc_type, exc_value, exc_tb = record.exc_info
            event["exc_type"] = exc_type.__name__
            event["exc_message"] = redact_sensitive(exc_value)
            event["exc_traceback"] = redact_sensitive(
                "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
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
        self._last_drop_report = 0.0
        self._dropped_reported = 0
        self._thread: threading.Thread | None = None

    # -- producer side (any thread; must never block or raise) --------------------

    def submit(self, event: str | dict[str, Any]) -> None:
        """Queue one record: normally its JSON text, encoded by the handler at log time."""
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
            self._maybe_report_drops()
            for _ in batch:
                self.queue.task_done()
            if stop:
                return

    def ship(self, batch: list[str | dict[str, Any]]) -> bool:
        """POST one batch. Never raises; returns whether Axiom accepted it.

        Items are normally JSON text already (``AxiomHandler`` encodes at log time);
        any dict is encoded here one by one, so a single unserialisable record is
        dropped and counted on its own instead of taking the batch with it.
        """
        encoded: list[str] = []
        for event in batch:
            if isinstance(event, str):
                encoded.append(event)
                continue
            try:
                encoded.append(json.dumps(event, default=str))
            except Exception as exc:  # noqa: BLE001 - e.g. a value whose __str__ raises
                self.record_failure(1, exc)
        if not encoded:
            return False
        try:
            body = ("[" + ",".join(encoded) + "]").encode("utf-8")
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
            self.record_failure(len(encoded), exc)
            return False

    def record_failure(self, n: int, exc: BaseException) -> None:
        """Count ``n`` records that will never ship; report to stderr (rate-limited)."""
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
            _stderr(
                f"[axiom] failed to ship {n} log record(s) to {self.dataset}: "
                f"{type(exc).__name__}: {exc} (failed so far: {failed}, dropped: {dropped})"
            )

    def _maybe_report_drops(self) -> None:
        """Report queue-full drops even while shipping succeeds (rate-limited)."""
        with self._lock:
            dropped = self.dropped_records
            new = dropped - self._dropped_reported
            now = time.monotonic()
            due = (
                self._last_drop_report == 0.0
                or now - self._last_drop_report >= FAILURE_REPORT_INTERVAL_S
            )
            if not (new > 0 and due):
                return
            self._dropped_reported = dropped
            self._last_drop_report = now
        _stderr(
            f"[axiom] log queue full: dropped {new} record(s) for {self.dataset} "
            f"(dropped so far: {dropped})"
        )

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
        """Signal the drain thread to exit and wait for it, within ``timeout_s`` in total.

        Past the deadline the daemon thread is abandoned with whatever it still holds.
        """
        thread = self._thread
        if thread is None:
            return
        deadline = time.monotonic() + max(0.0, timeout_s)
        try:
            self.queue.put(self._STOP, timeout=max(0.0, timeout_s))
        except queue.Full:
            _stderr("[axiom] log queue still full at shutdown; abandoning it")
        else:
            thread.join(timeout=max(0.0, deadline - time.monotonic()))
        self._thread = None


def _stderr(message: str) -> None:
    try:
        print(message, file=sys.stderr, flush=True)
    except Exception:  # noqa: BLE001 - stderr itself may be gone at exit
        pass


class AxiomHandler(logging.Handler):
    """Logging handler that formats and JSON-encodes on the caller's thread, then enqueues.

    Encoding at log time freezes the record (later mutation of a logged object can't
    change what ships) and confines a record that can't be encoded to itself.
    """

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
            event = self.event_formatter.to_event(record)
        except Exception:  # noqa: BLE001 - logging must never raise into the app
            self.handleError(record)
            return
        try:
            encoded = json.dumps(event, default=str)
        except Exception as exc:  # noqa: BLE001 - e.g. an extra= value whose __str__ raises
            self.shipper.record_failure(1, exc)
            return
        self.shipper.submit(encoded)


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

        # httpx logs every request URL at INFO; with root lowered to INFO those lines
        # would ship. Hold them at WARNING unless something configured them already.
        for name in ("httpx", "httpcore"):
            lib_logger = logging.getLogger(name)
            if lib_logger.level == logging.NOTSET:
                lib_logger.setLevel(logging.WARNING)

        shipper.start()
        _shipper = shipper
    except Exception as exc:  # noqa: BLE001 - observability setup must not stop startup
        print(f"[axiom] log shipping disabled, setup failed: {exc!r}", file=sys.stderr)
        shutdown_axiom_logging()
        return None
    return target


def shutdown_axiom_logging() -> None:
    """Flush, stop the drain thread and detach only the handlers we installed.

    Flush and stop share one ``SHUTDOWN_TIMEOUT_S`` budget, so a hung Axiom delays
    process exit by at most that long in total.
    """
    global _shipper
    if _shipper is not None:
        deadline = time.monotonic() + SHUTDOWN_TIMEOUT_S
        _shipper.flush(SHUTDOWN_TIMEOUT_S)
        _shipper.stop(deadline - time.monotonic())
        _shipper = None
    while _installed:
        lg, handler = _installed.pop()
        lg.removeHandler(handler)


def current_shipper() -> AxiomShipper | None:
    return _shipper


atexit.register(shutdown_axiom_logging)
