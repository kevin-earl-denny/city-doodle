"""FastAPI application entry point."""

import logging
import re
import traceback

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.exc import DBAPIError, DataError, IntegrityError, OperationalError

from city_api.config import settings
from city_api.observability import configure_axiom_logging
from city_api.request_logging import RequestLoggingMiddleware
from city_api.routers import auth_router
from city_api.routes import (
    brief_router,
    cities_router,
    city_limits_router,
    districts_router,
    jobs_router,
    locks_router,
    neighborhoods_router,
    pois_router,
    road_network_router,
    seeds_router,
    tiles_router,
    transit_router,
    worlds_router,
)

logger = logging.getLogger(__name__)

# CITY-642: ship logs to Axiom when AXIOM_API_TOKEN is set; a no-op otherwise. Runs at
# import, i.e. after uvicorn has applied its own logging config, so attaching to the
# non-propagating `uvicorn` logger also ships uvicorn's startup/error lines.
configure_axiom_logging(
    service="api",
    app_env=settings.app_env,
    api_token=settings.axiom_api_token,
    org_id=settings.axiom_org_id,
    dataset=settings.axiom_dataset,
    dataset_dev=settings.axiom_dataset_dev,
    log_level=settings.log_level,
    extra_loggers=("uvicorn",),
    preserve_stderr_fallback=True,
)

app = FastAPI(
    title="City Doodle API",
    description="Backend API for City Doodle - a lo-fi vector city builder",
    version="0.1.0",
)

# CORS middleware - allow frontend origins
origins = list(settings.cors_origins)
if settings.frontend_url and settings.frontend_url not in origins:
    origins.append(settings.frontend_url)

# Regex pattern for Vercel preview deployments
# Matches: https://city-doodle-web-*.vercel.app
vercel_preview_regex = r"https://city-doodle-web-[a-z0-9]+-[a-z0-9]+\.vercel\.app"

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=vercel_preview_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# CITY-511: Compress responses > 1KB for 50-80% bandwidth reduction on JSON payloads
app.add_middleware(GZipMiddleware, minimum_size=1000)

# CITY-642: added last so it is the outermost user middleware (just inside Starlette's
# ServerErrorMiddleware): it times the whole stack, sees the final status, and binds
# its request_id for every log line emitted inside the request.
app.add_middleware(RequestLoggingMiddleware)

app.include_router(auth_router)
app.include_router(cities_router)
app.include_router(city_limits_router)
app.include_router(brief_router)
app.include_router(worlds_router)
app.include_router(tiles_router)
app.include_router(locks_router)
app.include_router(jobs_router)
app.include_router(seeds_router)
app.include_router(districts_router)
app.include_router(neighborhoods_router)
app.include_router(pois_router)
app.include_router(road_network_router)
app.include_router(transit_router)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "service": "city-api"}


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


# CITY-642: these handler lines can ship to Axiom, a durable, queryable store. So
# they log the path (never the query string) and drop Postgres DETAIL lines, which
# echo row values such as `Key (email)=(...) already exists`. SQL parameters are
# kept out by `hide_parameters=True` on the engine (city_api.database).
_DETAIL_LINE = re.compile(r"^\s*DETAIL:.*$\n?", re.MULTILINE)


def _redact_db_text(text: object) -> str:
    """Drop Postgres DETAIL lines (they carry row values) from an error/traceback string."""
    return _DETAIL_LINE.sub("", str(text))


@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError):
    """Handle database integrity errors (unique constraint, foreign key violations).

    Returns 409 Conflict for constraint violations.
    """
    logger.warning(
        f"Database integrity error on {request.method} {request.url.path}: "
        f"{_redact_db_text(exc.orig)}"
    )
    # Extract useful error message from the exception
    error_msg = str(exc.orig) if exc.orig else str(exc)

    # Check for specific constraint types
    if "foreign key" in error_msg.lower():
        detail = "Referenced resource does not exist"
    elif "unique" in error_msg.lower() or "duplicate" in error_msg.lower():
        detail = "Resource already exists"
    else:
        detail = "Database constraint violation"

    return JSONResponse(
        status_code=409,
        content={"detail": detail, "error_type": "IntegrityError"},
    )


@app.exception_handler(OperationalError)
async def operational_error_handler(request: Request, exc: OperationalError):
    """Handle database operational errors (connection issues, timeouts).

    Returns 503 Service Unavailable for database connectivity issues.
    """
    logger.error(
        f"Database operational error on {request.method} {request.url.path}: "
        f"{_redact_db_text(exc)}\n{_redact_db_text(traceback.format_exc())}"
    )
    return JSONResponse(
        status_code=503,
        content={
            "detail": "Database temporarily unavailable",
            "error_type": "OperationalError",
        },
    )


@app.exception_handler(DataError)
async def data_error_handler(request: Request, exc: DataError):
    """Handle database data errors (invalid data types, out of range values).

    Returns 400 Bad Request for invalid data.
    """
    logger.warning(
        f"Database data error on {request.method} {request.url.path}: "
        f"{_redact_db_text(exc.orig)}"
    )
    return JSONResponse(
        status_code=400,
        content={
            "detail": "Invalid data format for database field",
            "error_type": "DataError",
        },
    )


@app.exception_handler(ValidationError)
async def validation_error_handler(request: Request, exc: ValidationError):
    """Handle Pydantic validation errors that occur in business logic.

    Note: FastAPI automatically handles request validation errors via RequestValidationError.
    This catches validation errors that occur during response serialization or
    in repository/service layer code.
    """
    logger.warning(
        f"Validation error on {request.method} {request.url.path}: {exc}"
    )
    return JSONResponse(
        status_code=422,
        content={
            "detail": "Data validation failed",
            "errors": exc.errors(),
            "error_type": "ValidationError",
        },
    )


@app.exception_handler(DBAPIError)
async def dbapi_error_handler(request: Request, exc: DBAPIError):
    """Handle database DBAPI errors not caught by more specific handlers.

    Catches asyncpg-specific exceptions (e.g. InternalServerError) that SQLAlchemy
    wraps as DBAPIError but not as OperationalError. Returns 503 to indicate the
    database is temporarily unavailable.
    """
    logger.error(
        f"Database DBAPI error on {request.method} {request.url.path}: "
        f"{_redact_db_text(exc)}\n{_redact_db_text(traceback.format_exc())}"
    )
    return JSONResponse(
        status_code=503,
        content={
            "detail": "Database temporarily unavailable",
            "error_type": "DBAPIError",
        },
    )


def _add_cors_headers(response: JSONResponse, request: Request) -> JSONResponse:
    """Add CORS headers to a response based on the request's Origin header."""
    origin = request.headers.get("origin")
    if not origin:
        return response

    allowed = origin in origins
    if not allowed and vercel_preview_regex:
        allowed = bool(re.match(vercel_preview_regex, origin))

    if allowed:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Vary"] = "Origin"

    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler that logs errors and returns proper JSON responses.

    IMPORTANT: Starlette routes @app.exception_handler(Exception) to
    ServerErrorMiddleware, which runs OUTSIDE the CORS middleware stack. This means
    responses from this handler do NOT get CORS headers automatically. We must add
    them manually so the frontend can read error responses instead of seeing
    opaque "Failed to fetch" CORS errors.
    """
    logger.error(
        f"Unhandled exception on {request.method} {request.url.path}: "
        f"{_redact_db_text(exc)}\n{_redact_db_text(traceback.format_exc())}"
    )
    response = JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "error_type": type(exc).__name__,
        },
    )
    return _add_cors_headers(response, request)
