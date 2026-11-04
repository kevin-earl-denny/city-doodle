"""Authentication router.

Sign-up, sign-in and sign-out are handled by Clerk in the web app (CITY-644);
the API only verifies Clerk session tokens (see city_api.clerk_auth).
"""

from typing import Annotated

from fastapi import APIRouter, Depends

from city_api.dependencies import get_current_user_model
from city_api.models import User
from city_api.schemas import UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: Annotated[User, Depends(get_current_user_model)],
) -> UserResponse:
    """Get the current authenticated user (linked or created on first Clerk sign-in)."""
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        created_at=current_user.created_at,
    )
