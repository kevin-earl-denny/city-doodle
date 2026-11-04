"""Call Claude to turn a terrain description into a WorldBrief."""

import json
import logging
import time
from collections import deque
from datetime import UTC, datetime
from uuid import UUID

import anthropic
import pydantic
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from city_api.brief.compiler import compile_brief
from city_api.brief.prompt import SYSTEM_PROMPT, build_user_message
from city_api.brief.schema import BriefRequest, WorldBrief
from city_api.config import settings

logger = logging.getLogger(__name__)


class BriefError(Exception):
    """Base error. `status` and `public_message` are safe to return to the client."""

    status = 502
    public_message = "The surveyor couldn't read that one. Try again in a moment."


class BriefUnavailableError(BriefError):
    status = 503
    public_message = "AI terrain isn't set up on this server yet."


class BriefRateLimitedError(BriefError):
    status = 429
    public_message = "Too many surveys at once. Give it a few seconds."


class BriefDailyCapError(BriefError):
    # 503, not 429: nothing a client can usefully retry until the UTC day rolls over.
    status = 503
    public_message = "The surveyors have clocked out for today. Try Draw it, or come back tomorrow."


class BriefRefusedError(BriefError):
    status = 422
    public_message = "The surveyor can't map that description. Try describing the land."


_client: anthropic.AsyncAnthropic | None = None


def _get_client() -> anthropic.AsyncAnthropic:
    global _client
    if not settings.brief_enabled or not settings.anthropic_api_key:
        raise BriefUnavailableError()
    if _client is None:
        # One retry with a 45s timeout keeps a slow request under ~90s wall clock.
        _client = anthropic.AsyncAnthropic(
            api_key=settings.anthropic_api_key, timeout=45.0, max_retries=1
        )
    return _client


# In-memory limits, per process. That's fine for a single API instance; move them to
# Redis if we scale horizontally. They bound Opus spend: a per-user sliding
# minute, a per-user day, and a global minute across all users.
_recent: dict[UUID, deque[float]] = {}
_daily: dict[UUID, deque[float]] = {}
_global: deque[float] = deque()
_DAY = 86_400.0


def _prune(window: deque[float], now: float, span: float) -> None:
    while window and now - window[0] > span:
        window.popleft()


def _evict_idle(table: dict[UUID, deque[float]], now: float, span: float) -> None:
    for key in [k for k, w in table.items() if not w or now - w[-1] > span]:
        del table[key]


def _check_rate_limit(user_id: UUID) -> float:
    """Raise if any per-process window is full, else record the call and return its stamp.

    Checking and recording happen with no await in between, so concurrent requests
    from one user can't all slip past the check before any of them is recorded.
    """
    now = time.monotonic()
    if len(_recent) > 1000:
        _evict_idle(_recent, now, 60)
        _evict_idle(_daily, now, _DAY)

    _prune(_global, now, 60)
    if len(_global) >= settings.brief_global_limit_per_minute:
        raise BriefRateLimitedError()

    minute = _recent.setdefault(user_id, deque())
    _prune(minute, now, 60)
    if len(minute) >= settings.brief_rate_limit_per_minute:
        raise BriefRateLimitedError()

    day = _daily.setdefault(user_id, deque())
    _prune(day, now, _DAY)
    if len(day) >= settings.brief_daily_limit_per_user:
        raise BriefRateLimitedError()

    minute.append(now)
    day.append(now)
    _global.append(now)
    return now


def _unrecord_call(user_id: UUID, stamp: float) -> None:
    """Give back a recorded slot, used when the global daily cap rejects the call."""
    for window in (_recent.get(user_id), _daily.get(user_id), _global):
        if window is None:
            continue
        try:
            window.remove(stamp)
        except ValueError:
            pass  # already pruned


# Atomic upsert: works on Postgres and SQLite (>= 3.35 for RETURNING).
_INCREMENT_SQL = text(
    "INSERT INTO brief_usage (day, count) VALUES (:day, 1) "
    "ON CONFLICT (day) DO UPDATE SET count = brief_usage.count + 1 "
    "RETURNING count"
)


async def _check_global_daily_cap(db: AsyncSession) -> None:
    """Count this call against the cross-machine daily cap (UTC day).

    The count goes up before the model call, so every attempt is counted.
    Failed calls still cost tokens, so that's the safe direction.
    """
    today = datetime.now(UTC).date()
    try:
        count = (await db.execute(_INCREMENT_SQL, {"day": today})).scalar_one()
        await db.commit()
    except (SQLAlchemyError, OSError) as e:
        # Fail closed: if we can't count, we don't spend.
        logger.error("brief: usage counter unavailable: %s", type(e).__name__)
        raise BriefUnavailableError() from e
    if count > settings.brief_global_daily_limit:
        logger.warning("brief: global daily cap reached (%s)", settings.brief_global_daily_limit)
        raise BriefDailyCapError()


async def generate_brief(request: BriefRequest, user_id: UUID, db: AsyncSession) -> WorldBrief:
    client = _get_client()
    # Record the per-process slot synchronously, before any await (that ordering
    # is what blocks concurrent bursts). If the shared daily cap then rejects
    # the call, give the slot back, so a global rejection doesn't cost the user.
    stamp = _check_rate_limit(user_id)
    try:
        await _check_global_daily_cap(db)
    except BriefError:
        _unrecord_call(user_id, stamp)
        raise

    previous = request.previous
    if previous is not None:
        # Client-echoed: re-normalise (clamps, consistency) before it reaches the prompt.
        previous = compile_brief(previous)[0]

    try:
        response = await client.beta.messages.parse(
            model=settings.brief_model,
            max_tokens=settings.brief_max_tokens,
            thinking={"type": "adaptive"},
            output_config={"effort": settings.brief_effort},
            # Re-run a refused request on a fallback model chosen by the API.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            system=[
                {
                    "type": "text",
                    "text": SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral", "ttl": "1h"},
                }
            ],
            messages=[
                {
                    "role": "user",
                    "content": build_user_message(request.prompt, previous, request.refinement),
                }
            ],
            output_format=WorldBrief,
        )
    except anthropic.RateLimitError as e:
        logger.warning("brief: anthropic rate limited: %s", e)
        raise BriefRateLimitedError() from e
    except anthropic.AuthenticationError as e:
        logger.error("brief: anthropic auth failed, check ANTHROPIC_API_KEY")
        raise BriefUnavailableError() from e
    except anthropic.APIStatusError as e:
        logger.error("brief: anthropic error status=%s request_id=%s", e.status_code, e.request_id)
        raise BriefError() from e
    except anthropic.APIConnectionError as e:
        logger.error("brief: anthropic connection error: %s", e)
        raise BriefError() from e
    except (pydantic.ValidationError, json.JSONDecodeError) as e:
        # parse() validates inside the call, so truncated or invalid JSON raises
        # here rather than reaching the stop_reason checks below. Log the
        # error type only; never echo model output to the client.
        logger.error("brief: model output failed validation: %s", type(e).__name__)
        raise BriefError() from e

    usage = response.usage
    logger.info(
        "brief: request_id=%s stop=%s in=%s cache_read=%s cache_write=%s out=%s",
        response._request_id,
        response.stop_reason,
        usage.input_tokens,
        usage.cache_read_input_tokens,
        usage.cache_creation_input_tokens,
        usage.output_tokens,
    )

    if response.stop_reason == "refusal":
        raise BriefRefusedError()
    if response.stop_reason == "max_tokens" or response.parsed_output is None:
        logger.error("brief: no parsed output (stop=%s)", response.stop_reason)
        raise BriefError()
    return response.parsed_output
