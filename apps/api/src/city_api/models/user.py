"""User and Session models for authentication."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from city_api.database import Base


class User(Base):
    """User account for authentication."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    # Legacy bcrypt hash from pre-Clerk email/password auth; unused since CITY-644.
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Clerk user id (JWT `sub`, "user_..."), set on first Clerk sign-in.
    clerk_user_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    sessions: Mapped[list["Session"]] = relationship("Session", back_populates="user")

    __table_args__ = (
        Index("ix_users_email", "email"),
        Index("ix_users_clerk_user_id", "clerk_user_id", unique=True),
    )


class Session(Base):
    """Legacy session-token table; unused since Clerk auth (CITY-644), drop in a follow-up."""

    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship("User", back_populates="sessions")

    __table_args__ = (
        Index("ix_sessions_token", "token"),
        Index("ix_sessions_user_id", "user_id"),
        Index("ix_sessions_expires_at", "expires_at"),
    )
