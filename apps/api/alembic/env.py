"""Alembic migration environment configuration."""

import os
import re
from logging.config import fileConfig

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool

load_dotenv()

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

from city_api.database import Base  # noqa: E402
import city_api.models  # noqa: E402, F401  -- import all models so Alembic metadata is complete

target_metadata = Base.metadata


def transform_url_for_sync(url: str) -> str:
    """Transform async database URL for sync psycopg2 usage.

    - Pins the psycopg2 driver explicitly: SQLAlchemy 2.1 made a bare
      postgresql:// URL default to psycopg 3, which isn't installed (CITY-681)
    - Converts ssl= back to sslmode= for psycopg2
    """
    url = re.sub(r"^postgresql(\+asyncpg)?://", "postgresql+psycopg2://", url)
    # Convert ssl= to sslmode= for psycopg2
    url = re.sub(r"\bssl=(\w+)", r"sslmode=\1", url)
    return url


def get_url():
    """Get database URL from environment."""
    # Prefer explicit sync URL, otherwise transform async URL
    sync_url = os.getenv("DATABASE_URL_SYNC")
    if sync_url:
        return transform_url_for_sync(sync_url)

    url = os.getenv("DATABASE_URL", "postgresql://localhost/city_doodle")
    return transform_url_for_sync(url)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = get_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
