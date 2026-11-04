"""User schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr


class UserBase(BaseModel):
    """Base user schema."""

    email: EmailStr


class UserResponse(UserBase):
    """User response schema."""

    id: UUID
    created_at: datetime

    class Config:
        from_attributes = True
