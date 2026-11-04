"""Call Claude to turn a terrain description into a WorldBrief."""

import logging
import time
from collections import defaultdict, deque
from uuid import UUID

import anthropic

from city_api.brief.prompt import SYSTEM_PROMPT, build_user_message
from city_api.brief.schema import BriefRequest, WorldBrief
from city_api.config import settings

logger = logging.getLogger(__name__)


class BriefError(Exception):
    """Base error. `status` and `public_message` are safe to return to the client."""

    status = 502
    public_message = "The surveyor couldn't read that one. Try again in a moment."


class BriefUnavailable(BriefError):
    status = 503
    public_message = "AI terrain isn't set up on this server yet."


class BriefRateLimited(BriefError):
    status = 429
    public_message = "Too many surveys at once. Give it a few seconds."


class BriefRefused(BriefError):
    status = 422
    public_message = "The surveyor can't map that description. Try describing the land."


_client: anthropic.AsyncAnthropic | None = None


def _get_client() -> anthropic.AsyncAnthropic:
    global _client
    if not settings.anthropic_api_key:
        raise BriefUnavailable()
    if _client is None:
        _client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key, timeout=90.0)
    return _client


# In-memory per-user sliding window. Per-process, which is fine for a single
# API instance. Move it to Redis if we scale horizontally.
_recent: dict[UUID, deque[float]] = defaultdict(deque)


def _check_rate_limit(user_id: UUID) -> None:
    window = _recent[user_id]
    now = time.monotonic()
    while window and now - window[0] > 60:
        window.popleft()
    if len(window) >= settings.brief_rate_limit_per_minute:
        raise BriefRateLimited()
    window.append(now)


async def generate_brief(request: BriefRequest, user_id: UUID) -> WorldBrief:
    client = _get_client()
    _check_rate_limit(user_id)

    try:
        response = await client.beta.messages.parse(
            model=settings.brief_model,
            max_tokens=16000,
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
                    "content": build_user_message(
                        request.prompt, request.previous, request.refinement
                    ),
                }
            ],
            output_format=WorldBrief,
        )
    except anthropic.RateLimitError as e:
        logger.warning("brief: anthropic rate limited: %s", e)
        raise BriefRateLimited() from e
    except anthropic.AuthenticationError as e:
        logger.error("brief: anthropic auth failed, check ANTHROPIC_API_KEY")
        raise BriefUnavailable() from e
    except anthropic.APIStatusError as e:
        logger.error("brief: anthropic error status=%s request_id=%s", e.status_code, e.request_id)
        raise BriefError() from e
    except anthropic.APIConnectionError as e:
        logger.error("brief: anthropic connection error: %s", e)
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
        raise BriefRefused()
    if response.stop_reason == "max_tokens" or response.parsed_output is None:
        logger.error("brief: no parsed output (stop=%s)", response.stop_reason)
        raise BriefError()
    return response.parsed_output
