"""Database connection and session management."""

import re
from collections.abc import AsyncGenerator

from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase


def transform_database_url_for_asyncpg(url: str) -> str:
    """Transform database URL for asyncpg compatibility.

    asyncpg doesn't support 'sslmode' parameter - it uses 'ssl' instead.
    This transforms Neon-style URLs (sslmode=require) to asyncpg-compatible URLs.
    """
    # Replace sslmode=require with ssl=require for asyncpg
    return re.sub(r"sslmode=(\w+)", r"ssl=\1", url)


# Database-agnostic JSON type: JSONB on Postgres, JSON on SQLite/others
# This allows tests to use SQLite while production uses Postgres JSONB
JSONVariant = JSON().with_variant(JSONB(), "postgresql")


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models."""

    pass


# Lazy-loaded engine and session factory (avoids import-time errors for Alembic)
_engine = None
_async_session = None


def get_engine():
    """Get or create the async engine."""
    global _engine
    if _engine is None:
        from city_api.config import settings

        # Transform URL for asyncpg compatibility (sslmode -> ssl)
        db_url = transform_database_url_for_asyncpg(settings.database_url)
        _engine = create_async_engine(
            db_url,
            echo=False,
            pool_size=2,
            max_overflow=3,
            pool_recycle=300,
            pool_pre_ping=True,
            # CITY-642: keep bound SQL parameters (session tokens, emails) out of
            # exception text, which is logged and may ship to Axiom.
            hide_parameters=True,
        )
    return _engine


def get_session_factory():
    """Get or create the async session factory."""
    global _async_session
    if _async_session is None:
        _async_session = async_sessionmaker(
            get_engine(), class_=AsyncSession, expire_on_commit=False
        )
    return _async_session


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency that yields a database session."""
    session_factory = get_session_factory()
    async with session_factory() as session:
        yield session
