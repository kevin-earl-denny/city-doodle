"""Pytest configuration and fixtures for API tests."""

import os
from collections.abc import AsyncGenerator
from uuid import UUID

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool, StaticPool

# Import all models so they are registered with Base.metadata
# This ensures tables are created during test setup
import city_api.models  # noqa: F401
from city_api.database import Base, get_db
from city_api.main import app

# Test user IDs (must match the ones used in test files)
TEST_USER_ID = UUID("00000000-0000-0000-0000-000000000001")
OTHER_USER_ID = UUID("00000000-0000-0000-0000-000000000002")

# Fixed test world and tile IDs for tests that need real entities
TEST_WORLD_ID = UUID("00000000-0000-0000-0000-000000000010")
TEST_TILE_ID = UUID("00000000-0000-0000-0000-000000000020")

# Use SQLite for local tests, PostgreSQL in CI (when TEST_DATABASE_URL is set)
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "sqlite+aiosqlite:///:memory:",
)

# Detect database type
is_sqlite = TEST_DATABASE_URL.startswith("sqlite")

# Lazy initialization for engine and session factory
# This avoids creating the engine at module import time, which would
# bind it to the wrong event loop when running tests in CI
_test_engine = None
_test_session_factory = None


def get_test_engine():
    """Get or create the test database engine lazily."""
    global _test_engine, _test_session_factory

    if _test_engine is None:
        if is_sqlite:
            # SQLite in-memory requires StaticPool to keep connection alive
            _test_engine = create_async_engine(
                TEST_DATABASE_URL,
                echo=False,
                connect_args={"check_same_thread": False},
                poolclass=StaticPool,
            )
        else:
            # PostgreSQL settings - use NullPool to avoid event loop issues
            _test_engine = create_async_engine(
                TEST_DATABASE_URL,
                echo=False,
                poolclass=NullPool,
            )

        _test_session_factory = async_sessionmaker(
            _test_engine, class_=AsyncSession, expire_on_commit=False
        )

    return _test_engine, _test_session_factory


# Note: Foreign key constraints are NOT enforced in SQLite tests for simplicity.
# The PostgreSQL tests in CI will enforce them properly.
# This allows tests to use arbitrary UUIDs without creating full entity hierarchies.


async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
    """Override database dependency for tests."""
    _, session_factory = get_test_engine()
    async with session_factory() as session:
        yield session


def _postgres_enum_types() -> list[PG_ENUM]:
    """Every Postgres ENUM the models use, deduplicated by type name.

    The models declare them with create_type=False because Alembic migrations
    own the types in real databases, so create_all/drop_all skip them. Tests
    build the schema with create_all, so they must create and drop the types.
    """
    enums: dict[str, PG_ENUM] = {}
    for table in Base.metadata.tables.values():
        for column in table.columns:
            if isinstance(column.type, PG_ENUM) and column.type.name:
                enums.setdefault(column.type.name, column.type)
    return list(enums.values())


@pytest.fixture(scope="session", autouse=True)
async def setup_test_db():
    """Create test database tables once per session."""
    engine, _ = get_test_engine()
    async with engine.begin() as conn:
        if not is_sqlite:
            # Start clean even if a previous run died before teardown.
            await conn.run_sync(Base.metadata.drop_all)
            for enum in _postgres_enum_types():
                await conn.run_sync(lambda sync_conn, e=enum: e.drop(sync_conn, checkfirst=True))
                await conn.run_sync(lambda sync_conn, e=enum: e.create(sync_conn, checkfirst=False))
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        if not is_sqlite:
            for enum in _postgres_enum_types():
                await conn.run_sync(lambda sync_conn, e=enum: e.drop(sync_conn, checkfirst=True))


@pytest.fixture(autouse=True)
async def clear_tables():
    """Clear all tables and create test users before each test."""
    engine, _ = get_test_engine()
    # Use a raw connection to avoid session state issues
    async with engine.connect() as conn:
        if "postgresql" in TEST_DATABASE_URL:
            await conn.execute(
                text(
                    "TRUNCATE users, sessions, worlds, tiles, tile_locks, jobs, placed_seeds, districts, road_nodes, road_edges, transit_stations, transit_lines, transit_line_segments, brief_usage RESTART IDENTITY CASCADE"
                )
            )
        else:
            await conn.execute(text("DELETE FROM tile_locks"))
            await conn.execute(text("DELETE FROM jobs"))
            await conn.execute(text("DELETE FROM placed_seeds"))
            await conn.execute(text("DELETE FROM transit_line_segments"))
            await conn.execute(text("DELETE FROM transit_lines"))
            await conn.execute(text("DELETE FROM transit_stations"))
            await conn.execute(text("DELETE FROM districts"))
            await conn.execute(text("DELETE FROM road_edges"))
            await conn.execute(text("DELETE FROM road_nodes"))
            await conn.execute(text("DELETE FROM tiles"))
            await conn.execute(text("DELETE FROM worlds"))
            await conn.execute(text("DELETE FROM sessions"))
            await conn.execute(text("DELETE FROM users"))
            await conn.execute(text("DELETE FROM brief_usage"))

        # Create test users that tests expect to exist
        # These are the user IDs used in X-User-Id headers during dev mode testing
        # Note: SQLite stores UUIDs without hyphens, Postgres stores with hyphens
        test_user_id_str = str(TEST_USER_ID).replace("-", "") if is_sqlite else str(TEST_USER_ID)
        other_user_id_str = str(OTHER_USER_ID).replace("-", "") if is_sqlite else str(OTHER_USER_ID)

        await conn.execute(
            text("INSERT INTO users (id, email, password_hash) VALUES (:id, :email, :hash)"),
            {
                "id": test_user_id_str,
                "email": "test@example.com",
                "hash": "$2b$12$placeholder",  # Fake hash, not used in tests
            },
        )
        await conn.execute(
            text("INSERT INTO users (id, email, password_hash) VALUES (:id, :email, :hash)"),
            {
                "id": other_user_id_str,
                "email": "other@example.com",
                "hash": "$2b$12$placeholder",
            },
        )

        # Create test world and tile for tests that need them
        test_world_id_str = str(TEST_WORLD_ID).replace("-", "") if is_sqlite else str(TEST_WORLD_ID)
        test_tile_id_str = str(TEST_TILE_ID).replace("-", "") if is_sqlite else str(TEST_TILE_ID)

        await conn.execute(
            text(
                "INSERT INTO worlds (id, user_id, name, seed, settings) VALUES (:id, :user_id, :name, :seed, :settings)"
            ),
            {
                "id": test_world_id_str,
                "user_id": test_user_id_str,
                "name": "Test World",
                "seed": 12345,
                "settings": "{}",
            },
        )
        await conn.execute(
            text(
                "INSERT INTO tiles (id, world_id, tx, ty, terrain_data, features, version) VALUES (:id, :world_id, :tx, :ty, :terrain_data, :features, :version)"
            ),
            {
                "id": test_tile_id_str,
                "world_id": test_world_id_str,
                "tx": 0,
                "ty": 0,
                "terrain_data": "{}",
                "features": "{}",
                "version": 1,
            },
        )
        await conn.commit()
    yield


@pytest_asyncio.fixture
async def client(setup_test_db):
    """Async test client for FastAPI app."""
    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def db_session(setup_test_db) -> AsyncGenerator[AsyncSession, None]:
    """Provide a database session for tests that need direct DB access."""
    _, session_factory = get_test_engine()
    async with session_factory() as session:
        yield session
