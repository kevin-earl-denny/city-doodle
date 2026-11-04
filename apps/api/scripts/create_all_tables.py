#!/usr/bin/env python3
"""Create all missing tables in the production database."""

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
        # =====================================================
        # ENUMS
        # =====================================================

        # district_type enum - matches frontend types
        conn.execute(
            text("""
            DO $$ BEGIN
                CREATE TYPE district_type AS ENUM (
                    'residential', 'downtown', 'commercial', 'industrial',
                    'hospital', 'university', 'k12', 'park', 'airport'
                );
            EXCEPTION WHEN duplicate_object THEN null;
            END $$;
        """)
        )
        print("✓ district_type enum")

        # station_type enum
        conn.execute(
            text("""
            DO $$ BEGIN
                CREATE TYPE station_type AS ENUM ('subway', 'rail');
            EXCEPTION WHEN duplicate_object THEN null;
            END $$;
        """)
        )
        print("✓ station_type enum")

        # line_type enum
        conn.execute(
            text("""
            DO $$ BEGIN
                CREATE TYPE line_type AS ENUM ('subway', 'rail', 'light_rail', 'bus');
            EXCEPTION WHEN duplicate_object THEN null;
            END $$;
        """)
        )
        print("✓ line_type enum")

        # road_class enum
        conn.execute(
            text("""
            DO $$ BEGIN
                CREATE TYPE road_class AS ENUM (
                    'highway', 'arterial', 'collector', 'local', 'alley', 'trail'
                );
            EXCEPTION WHEN duplicate_object THEN null;
            END $$;
        """)
        )
        print("✓ road_class enum")

        # node_type enum
        conn.execute(
            text("""
            DO $$ BEGIN
                CREATE TYPE node_type AS ENUM (
                    'intersection', 'endpoint', 'roundabout', 'interchange'
                );
            EXCEPTION WHEN duplicate_object THEN null;
            END $$;
        """)
        )
        print("✓ node_type enum")

        # =====================================================
        # TABLES
        # =====================================================

        # placed_seeds table
        conn.execute(
            text("""
            CREATE TABLE IF NOT EXISTS placed_seeds (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                world_id UUID NOT NULL REFERENCES worlds(id) ON DELETE CASCADE,
                seed_type VARCHAR(50) NOT NULL,
                x FLOAT NOT NULL,
                y FLOAT NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
            )
        """)
        )
        conn.execute(
            text("CREATE INDEX IF NOT EXISTS ix_placed_seeds_world_id ON placed_seeds(world_id)")
        )
        print("✓ placed_seeds table")

        # road_nodes table
        conn.execute(
            text("""
            CREATE TABLE IF NOT EXISTS road_nodes (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                world_id UUID NOT NULL REFERENCES worlds(id) ON DELETE CASCADE,
                x FLOAT NOT NULL,
                y FLOAT NOT NULL,
                node_type node_type NOT NULL DEFAULT 'intersection',
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
            )
        """)
        )
        conn.execute(
            text("CREATE INDEX IF NOT EXISTS ix_road_nodes_world_id ON road_nodes(world_id)")
        )
        print("✓ road_nodes table")

        # road_edges table
        conn.execute(
            text("""
            CREATE TABLE IF NOT EXISTS road_edges (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                world_id UUID NOT NULL REFERENCES worlds(id) ON DELETE CASCADE,
                start_node_id UUID NOT NULL REFERENCES road_nodes(id) ON DELETE CASCADE,
                end_node_id UUID NOT NULL REFERENCES road_nodes(id) ON DELETE CASCADE,
                road_class road_class NOT NULL DEFAULT 'local',
                name VARCHAR(255),
                geometry JSONB,
                length FLOAT,
                speed_limit INTEGER,
                lanes INTEGER DEFAULT 2,
                oneway BOOLEAN DEFAULT false,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
            )
        """)
        )
        conn.execute(
            text("CREATE INDEX IF NOT EXISTS ix_road_edges_world_id ON road_edges(world_id)")
        )
        conn.execute(
            text("CREATE INDEX IF NOT EXISTS ix_road_edges_start_node ON road_edges(start_node_id)")
        )
        conn.execute(
            text("CREATE INDEX IF NOT EXISTS ix_road_edges_end_node ON road_edges(end_node_id)")
        )
        conn.execute(
            text("CREATE INDEX IF NOT EXISTS ix_road_edges_class ON road_edges(road_class)")
        )
        print("✓ road_edges table")

        # districts table
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
        print("✓ districts table")

        # transit_stations table
        conn.execute(
            text("""
            CREATE TABLE IF NOT EXISTS transit_stations (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                world_id UUID NOT NULL REFERENCES worlds(id) ON DELETE CASCADE,
                station_type station_type NOT NULL,
                name VARCHAR(255) NOT NULL,
                x FLOAT NOT NULL,
                y FLOAT NOT NULL,
                is_transfer BOOLEAN NOT NULL DEFAULT false,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
            )
        """)
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_transit_stations_world_id ON transit_stations(world_id)"
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_transit_stations_type ON transit_stations(station_type)"
            )
        )
        print("✓ transit_stations table")

        # transit_lines table
        conn.execute(
            text("""
            CREATE TABLE IF NOT EXISTS transit_lines (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                world_id UUID NOT NULL REFERENCES worlds(id) ON DELETE CASCADE,
                line_type line_type NOT NULL,
                name VARCHAR(255) NOT NULL,
                color VARCHAR(7),
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
            )
        """)
        )
        conn.execute(
            text("CREATE INDEX IF NOT EXISTS ix_transit_lines_world_id ON transit_lines(world_id)")
        )
        print("✓ transit_lines table")

        # transit_line_segments table
        conn.execute(
            text("""
            CREATE TABLE IF NOT EXISTS transit_line_segments (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                line_id UUID NOT NULL REFERENCES transit_lines(id) ON DELETE CASCADE,
                from_station_id UUID NOT NULL REFERENCES transit_stations(id) ON DELETE CASCADE,
                to_station_id UUID NOT NULL REFERENCES transit_stations(id) ON DELETE CASCADE,
                sequence_order INTEGER NOT NULL,
                travel_time_minutes FLOAT,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
            )
        """)
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_transit_segments_line_id ON transit_line_segments(line_id)"
            )
        )
        print("✓ transit_line_segments table")

        # neighborhoods table
        conn.execute(
            text("""
            CREATE TABLE IF NOT EXISTS neighborhoods (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                world_id UUID NOT NULL REFERENCES worlds(id) ON DELETE CASCADE,
                name VARCHAR(255) NOT NULL,
                geometry JSONB NOT NULL,
                fill_color VARCHAR(7) DEFAULT '#3B82F6',
                stroke_color VARCHAR(7) DEFAULT '#1D4ED8',
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
            )
        """)
        )
        conn.execute(
            text("CREATE INDEX IF NOT EXISTS ix_neighborhoods_world_id ON neighborhoods(world_id)")
        )
        print("✓ neighborhoods table")

        conn.commit()
        print("\n✅ All tables created successfully!")


if __name__ == "__main__":
    main()
