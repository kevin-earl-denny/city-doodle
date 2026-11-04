"""FastAPI dependencies for City Doodle API."""

from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from city_api.clerk_auth import resolve_clerk_user, verify_bearer_token
from city_api.config import settings
from city_api.database import get_db
from city_api.models import User

# Placeholder user ID for development mode
DEV_USER_ID = UUID("00000000-0000-0000-0000-000000000001")


def _dev_user_id(x_user_id: str | None) -> UUID:
    """Dev mode: use the X-User-Id header, or fall back to DEV_USER_ID."""
    if not x_user_id:
        return DEV_USER_ID
    try:
        return UUID(x_user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format",
        )


async def get_current_user_model(
    authorization: str | None = Header(default=None),
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Get the current authenticated user as a User model.

    In dev mode (AUTH_MODE=dev, local/tests only; refused on Fly):
        - Accepts X-User-Id header for testing, else DEV_USER_ID; the user must exist

    In production mode (AUTH_MODE=production):
        - Requires Authorization: Bearer <Clerk session JWT>
        - Verifies it against the Clerk JWKS, then resolves/links/creates the
          local user (see city_api.clerk_auth)
        - Returns 401 if the token is missing, invalid, or expired
    """
    if settings.auth_mode == "dev":
        user_id = _dev_user_id(x_user_id)
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
            )
        return user

    claims = await verify_bearer_token(authorization)
    return await resolve_clerk_user(db, claims["sub"])


async def get_current_user(
    authorization: str | None = Header(default=None),
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    db: AsyncSession = Depends(get_db),
) -> UUID:
    """Get the current authenticated user ID (see get_current_user_model).

    Always resolves the user row, so in dev mode an X-User-Id that does not
    match an existing user is rejected with 401.
    """
    user = await get_current_user_model(authorization, x_user_id, db)
    return user.id
