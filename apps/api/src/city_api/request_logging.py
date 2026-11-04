"""Per-request structured log line (CITY-642).

One ``event=request`` record per HTTP request with request id, method, route template,
path, status, duration and (when something binds it) user id. Every other line logged
while the request is in flight carries the same ``request_id`` through the log context.

Records are logged at INFO (``/health`` at DEBUG so Fly's health check doesn't flood the
dataset), which is below the root logger's default WARNING. With Axiom unset nothing
prints, so stdout is unchanged; 5xx are found by ``status >= 500`` rather than by level.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from city_api.observability import (
    bind_log_context,
    get_log_context,
    request_id_from,
    reset_log_context,
)

logger = logging.getLogger("city_api.request")

REQUEST_ID_HEADER = "x-request-id"
QUIET_PATHS = frozenset({"/health"})


def _route_template(scope: dict[str, Any]) -> str | None:
    route = scope.get("route")
    return getattr(route, "path", None)


class RequestLoggingMiddleware:
    """Pure ASGI middleware (no BaseHTTPMiddleware: it buffers and breaks contextvars)."""

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers") or [])
        raw_rid = headers.get(REQUEST_ID_HEADER.encode())
        request_id = request_id_from(raw_rid.decode("latin-1") if raw_rid else None)
        token = bind_log_context(request_id=request_id)
        start = time.perf_counter()
        status: int | None = None

        async def send_wrapper(message: dict[str, Any]) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                message.setdefault("headers", [])
                message["headers"] = [
                    *message["headers"],
                    (REQUEST_ID_HEADER.encode(), request_id.encode()),
                ]
            await send(message)

        exc_info = None
        try:
            await self.app(scope, receive, send_wrapper)
        except Exception as exc:
            # The global exception handler (outside this middleware) turns this into a 500.
            status = status or 500
            exc_info = (type(exc), exc, exc.__traceback__)
            raise
        finally:
            path = scope.get("path", "")
            fields = {
                "event": "request",
                "method": scope.get("method"),
                "route": _route_template(scope),
                "path": path,
                "status": status,
                "duration_ms": round((time.perf_counter() - start) * 1000, 1),
            }
            user_id = get_log_context().get("user_id")
            if user_id is not None:
                fields["user_id"] = str(user_id)
            level = logging.DEBUG if path in QUIET_PATHS else logging.INFO
            try:
                logger.log(
                    level,
                    "%s %s -> %s",
                    fields["method"],
                    fields["route"] or path,
                    status,
                    extra=fields,
                    exc_info=exc_info,
                )
            finally:
                reset_log_context(token)
