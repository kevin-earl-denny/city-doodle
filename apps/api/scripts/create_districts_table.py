#!/usr/bin/env python3
"""Manually create districts table if it doesn't exist."""

import os
import re

from sqlalchemy import create_engine, text


def transform_url(url: str) -> str:
    """Transform async URL to sync."""
    url = url.replace("postgresql+asyncpg://", "postgresql://")
    url = re.sub(r"ssl=(\w+)", r"sslmode=\1", url)
    return url


def main():
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        print("DATABASE_URL not set")
        return

    url = transform_url(url)
    engine = create_engine(url)

    with engine.connect() as conn:
        # Create district_type enum if it doesn't exist - matches frontend types
        conn.execute(
            text("""
            DO $$ BEGIN
                CREATE TYPE district_type AS ENUM (
                    'residential',
                    'downtown',
                    'commercial',
                    'industrial',
                    'hospital',
                    'university',
                    'k12',
                    'park',
                    'airport'
                );
            EXCEPTION
                WHEN duplicate_object THEN null;
            END $$;
        """)
        )
        print("district_type enum ready")

        # Create districts table
        conn.execute(
            text("""
            CREATE TABLE IF NOT EXISTS districts (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                world_id UUID NOT NULL REFERENCES worlds(id) ON DELETE CASCADE,
                type district_type NOT NULL,
                name VARCHAR(255),
                geometry JSONB NOT NULL,
                density FLOAT NOT NULL DEFAULT 1.0,
                max_height INTEGER NOT NULL DEFAULT 4,
                transit_access BOOLEAN NOT NULL DEFAULT false,
                historic BOOLEAN NOT NULL DEFAULT false,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
            )
        """)
        )
        conn.execute(
            text("CREATE INDEX IF NOT EXISTS ix_districts_world_id ON districts(world_id)")
        )
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_districts_type ON districts(type)"))
        conn.execute(
            text("CREATE INDEX IF NOT EXISTS ix_districts_historic ON districts(historic)")
        )
        conn.commit()
        print("Districts table created successfully")


if __name__ == "__main__":
    main()
