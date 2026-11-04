"""Add transit stations, lines, and segments tables

Revision ID: 009
Revises: 008
Create Date: 2026-02-04

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "009"
down_revision: str = "008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create station_type enum
    station_type = postgresql.ENUM(
        "subway",
        "rail",
        name="station_type",
        create_type=False,  # created explicitly below; True would re-CREATE it in create_table (CITY-684)
    )
    station_type.create(op.get_bind(), checkfirst=True)

    # Create line_type enum
    line_type = postgresql.ENUM(
        "subway",
        "rail",
        name="line_type",
        create_type=False,  # created explicitly below; True would re-CREATE it in create_table (CITY-684)
    )
    line_type.create(op.get_bind(), checkfirst=True)

    # Create transit_stations table
    op.create_table(
        "transit_stations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "world_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("worlds.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "district_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("districts.id", ondelete="SET NULL"),
            nullable=False,
        ),
        sa.Column("station_type", station_type, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("position_x", sa.Float, nullable=False),
        sa.Column("position_y", sa.Float, nullable=False),
        sa.Column("is_terminus", sa.Boolean, nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_transit_stations_world_id", "transit_stations", ["world_id"])
    op.create_index("ix_transit_stations_district_id", "transit_stations", ["district_id"])
    op.create_index("ix_transit_stations_station_type", "transit_stations", ["station_type"])

    # Create transit_lines table
    op.create_table(
        "transit_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "world_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("worlds.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("line_type", line_type, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("color", sa.String(7), nullable=False, server_default="'#FF0000'"),
        sa.Column("is_auto_generated", sa.Boolean, nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_transit_lines_world_id", "transit_lines", ["world_id"])
    op.create_index("ix_transit_lines_line_type", "transit_lines", ["line_type"])

    # Create transit_line_segments table
    op.create_table(
        "transit_line_segments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "line_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("transit_lines.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "from_station_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("transit_stations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "to_station_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("transit_stations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("geometry", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("is_underground", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("order_in_line", sa.Integer, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_transit_line_segments_line_id", "transit_line_segments", ["line_id"])
    op.create_index(
        "ix_transit_line_segments_from_station_id", "transit_line_segments", ["from_station_id"]
    )
    op.create_index(
        "ix_transit_line_segments_to_station_id", "transit_line_segments", ["to_station_id"]
    )
    op.create_index(
        "ix_transit_line_segments_order", "transit_line_segments", ["line_id", "order_in_line"]
    )


def downgrade() -> None:
    op.drop_table("transit_line_segments")
    op.drop_table("transit_lines")
    op.drop_table("transit_stations")

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS line_type")
    op.execute("DROP TYPE IF EXISTS station_type")
