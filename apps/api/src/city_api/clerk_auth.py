"""Clerk authentication: session-JWT verification and user resolution (CITY-644).

Flow for every authenticated request (AUTH_MODE=production):

1. ``verify_clerk_token`` checks the ``Authorization: Bearer <jwt>`` session token:
   RS256 signature against the instance JWKS (``https://<CLERK_DOMAIN>/.well-known/jwks.json``,
   keys cached by PyJWKClient), ``exp``/``nbf``/``iat``, ``iss`` == ``https://<CLERK_DOMAIN>``,
   a ``sid`` claim (only Clerk *session* tokens carry one, so JWT-template tokens signed by
   the same keys are refused) and ``azp`` against the allowed origins (required when
   CLERK_AUTHORIZED_PARTIES is set, otherwise checked when present).
2. ``resolve_clerk_user`` maps the Clerk user id (``sub``) to a local ``User``:
   by ``users.clerk_user_id``; else, on first sign-in, by the Clerk account's primary
   email **only if Clerk reports it verified** (links pre-Clerk accounts so they keep
   their worlds); else creates a new user. Linking/creation is race-safe: the unique
   constraints on ``users.clerk_user_id`` / ``users.email`` plus a guarded UPDATE make a
   concurrent first request lose cleanly, and the loser re-reads the winner's row.

Clerk session tokens carry no email claim by default, so the email comes from the
Clerk Backend API (``CLERK_SECRET_KEY``), and only on a user's first request.
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from typing import Any

import httpx
import jwt
from fastapi import HTTPException, status
from jwt import PyJWKClient
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from city_api.config import settings
from city_api.models import User

logger = logging.getLogger(__name__)

CLERK_API_BASE = "https://api.clerk.com/v1"
_HTTP_TIMEOUT_SECS = 5.0
# JWKS fetch timeout. PyJWKClient (>=2.14) holds a client-wide lock while it
# refetches on a signing-key cache miss, so keep a slow endpoint from queueing
# auth threads for PyJWT's default 30s. Known kids are served from the
# lru_cache (cache_keys=True) without taking that lock, and unknown-kid
# refetches are rate-limited by PyJWKClient's 30s cooldown.
_JWKS_TIMEOUT_SECS = 5.0
# Small clock-skew allowance; Clerk session tokens live ~60s.
_LEEWAY_SECS = 5
_RESOLVE_ATTEMPTS = 3

_jwks_client: PyJWKClient | None = None
_jwks_client_domain: str | None = None


class ClerkNotConfiguredError(RuntimeError):
    """AUTH_MODE=production but CLERK_DOMAIN is not set."""


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _issuer() -> str:
    return f"https://{settings.clerk_domain}"


def get_jwks_client() -> PyJWKClient:
    """Lazily create (and cache) the JWKS client for the configured Clerk domain."""
    global _jwks_client, _jwks_client_domain
    if not settings.clerk_domain:
        raise ClerkNotConfiguredError("CLERK_DOMAIN is not set")
    if _jwks_client is None or _jwks_client_domain != settings.clerk_domain:
        _jwks_client = PyJWKClient(
            f"{_issuer()}/.well-known/jwks.json",
            cache_keys=True,
            lifespan=3600,
            timeout=_JWKS_TIMEOUT_SECS,
        )
        _jwks_client_domain = settings.clerk_domain
    return _jwks_client


def _authorized_party_allowed(azp: str) -> bool:
    allowed = list(settings.clerk_authorized_parties)
    if not allowed:
        allowed = list(settings.cors_origins)
        if settings.frontend_url:
            allowed.append(settings.frontend_url)
    if azp in allowed:
        return True
    pattern = settings.clerk_authorized_party_regex
    return bool(pattern and re.fullmatch(pattern, azp))


def verify_clerk_token(token: str) -> dict[str, Any]:
    """Verify a Clerk session JWT and return its claims.

    Raises ``jwt.PyJWTError`` on any validation failure (including JWKS fetch
    failures, ``PyJWKClientError``) and ``ClerkNotConfiguredError`` when
    CLERK_DOMAIN is unset. Blocking on a JWKS cache miss; call via a thread.
    """
    signing_key = get_jwks_client().get_signing_key_from_jwt(token)
    claims = jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256"],
        issuer=_issuer(),
        leeway=_LEEWAY_SECS,
        options={"require": ["sub", "exp", "iat", "iss", "sid"]},
    )
    azp = claims.get("azp")
    if azp is None:
        if settings.clerk_authorized_parties:
            raise jwt.MissingRequiredClaimError("azp")
    elif not _authorized_party_allowed(azp):
        raise jwt.InvalidTokenError(f"azp {azp!r} is not an authorized party")
    return claims


async def verify_bearer_token(authorization: str | None) -> dict[str, Any]:
    """Validate an ``Authorization`` header value; HTTP 401 on any problem."""
    if not authorization:
        raise _unauthorized("Missing authorization header")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise _unauthorized("Invalid authorization header format")
    try:
        # PyJWKClient uses blocking urllib on a cache miss; keep it off the loop.
        return await asyncio.to_thread(verify_clerk_token, token.strip())
    except ClerkNotConfiguredError:
        logger.error("AUTH_MODE=production but CLERK_DOMAIN is not set; rejecting request")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is not configured",
        )
    except jwt.PyJWTError as exc:
        logger.info("Clerk JWT rejected: %s", exc)
        raise _unauthorized("Invalid or expired token")


@dataclass(frozen=True)
class ClerkEmail:
    """A Clerk user's primary email address and whether Clerk verified it."""

    address: str
    verified: bool


async def fetch_clerk_primary_email(clerk_user_id: str) -> ClerkEmail | None:
    """Return the primary email of a Clerk user from the Clerk Backend API.

    ``None`` when the user has no primary email. Raises ``HTTPException(401)``
    if Clerk no longer knows the user (deleted after the token was issued), and
    ``HTTPException(503)`` if Clerk is unreachable or CLERK_SECRET_KEY is
    missing, so a transient failure never creates a duplicate account.
    """
    if not settings.clerk_secret_key:
        logger.error("CLERK_SECRET_KEY is not set; cannot resolve first-time Clerk user")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is not configured",
        )
    try:
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT_SECS) as client:
            resp = await client.get(
                f"{CLERK_API_BASE}/users/{clerk_user_id}",
                headers={"Authorization": f"Bearer {settings.clerk_secret_key}"},
            )
            if resp.status_code == 404:
                logger.info("Clerk user %s not found; rejecting token", clerk_user_id)
                raise _unauthorized("Unknown user")
            resp.raise_for_status()
            data = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("Clerk user lookup failed for %s: %s", clerk_user_id, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not reach the authentication provider",
        )
    return primary_email_from_clerk_user(data)


def primary_email_from_clerk_user(user: dict[str, Any]) -> ClerkEmail | None:
    """Extract the primary email + verification status from a Clerk user payload."""
    primary_id = user.get("primary_email_address_id")
    for addr in user.get("email_addresses") or []:
        if addr.get("id") == primary_id and addr.get("email_address"):
            verification = addr.get("verification") or {}
            return ClerkEmail(
                address=addr["email_address"],
                verified=verification.get("status") == "verified",
            )
    return None


async def _get_by_clerk_id(db: AsyncSession, clerk_user_id: str) -> User | None:
    result = await db.execute(select(User).where(User.clerk_user_id == clerk_user_id))
    return result.scalar_one_or_none()


async def _get_by_email(db: AsyncSession, email: str) -> User | None:
    """Find an existing user by email, case-insensitively (legacy rows keep their casing)."""
    result = await db.execute(
        select(User).where(func.lower(User.email) == email.lower()).order_by(User.created_at)
    )
    matches = list(result.scalars().all())
    if len(matches) > 1:
        exact = [u for u in matches if u.email == email]
        if len(exact) != 1:
            logger.error("Multiple users match email for Clerk link; refusing to guess")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Multiple accounts share this email; contact support",
            )
        return exact[0]
    return matches[0] if matches else None


async def resolve_clerk_user(db: AsyncSession, clerk_user_id: str) -> User:
    """Return the local user for a verified Clerk user id, linking or creating it."""
    user = await _get_by_clerk_id(db, clerk_user_id)
    if user is not None:
        return user

    email = await fetch_clerk_primary_email(clerk_user_id)
    if email is None or not email.verified:
        # Never link (or create, which could collide with an existing account's
        # email) on an unverified address.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="A verified primary email address is required",
        )

    for _ in range(_RESOLVE_ATTEMPTS):
        user = await _get_by_clerk_id(db, clerk_user_id)
        if user is not None:
            return user

        existing = await _get_by_email(db, email.address)
        if existing is not None:
            if existing.clerk_user_id not in (None, clerk_user_id):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="This email is already linked to a different sign-in",
                )
            # Guarded link: only claims a row that is still unlinked.
            result = await db.execute(
                update(User)
                .where(User.id == existing.id, User.clerk_user_id.is_(None))
                .values(clerk_user_id=clerk_user_id)
                .execution_options(synchronize_session=False)
            )
            await db.commit()
            if result.rowcount == 1:
                logger.info("Linked existing user %s to Clerk user %s", existing.id, clerk_user_id)
            # rowcount 0: a concurrent request linked it first; loop re-reads.
            db.expire_all()
            continue

        db.add(User(email=email.address, clerk_user_id=clerk_user_id, password_hash=None))
        try:
            await db.commit()
        except IntegrityError:
            # Lost a race on clerk_user_id or email; re-read on the next pass.
            await db.rollback()
            continue
        logger.info("Created user for Clerk user %s", clerk_user_id)

    user = await _get_by_clerk_id(db, clerk_user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Could not link this sign-in to an account",
        )
    return user
