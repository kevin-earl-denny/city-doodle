"""Add road network tables (nodes and edges)

Revision ID: 007
Revises: 006
Create Date: 2026-02-04

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "007"
down_revision: str = "006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create enum types
    node_type = postgresql.ENUM(
        "intersection",
        "endpoint",
        "roundabout",
        "interchange",
        name="node_type",
        create_type=False,  # created explicitly below; True would re-CREATE it in create_table (CITY-684)
    )
    node_type.create(op.get_bind(), checkfirst=True)

    road_class = postgresql.ENUM(
        "highway",
        "arterial",
        "collector",
        "local",
        "alley",
        name="road_class",
        create_type=False,  # created explicitly below; True would re-CREATE it in create_table (CITY-684)
    )
    road_class.create(op.get_bind(), checkfirst=True)

    # Create road_nodes table
    op.create_table(
        "road_nodes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "world_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("worlds.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("position", postgresql.JSONB, nullable=False),
        sa.Column(
            "node_type",
            node_type,
            nullable=False,
            server_default="intersection",
        ),
        sa.Column("name", sa.String(255), nullable=True),
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
    op.create_index("ix_road_nodes_world_id", "road_nodes", ["world_id"])

    # Create road_edges table
    op.create_table(
        "road_edges",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "world_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("worlds.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "from_node_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("road_nodes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "to_node_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("road_nodes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "road_class",
            road_class,
            nullable=False,
            server_default="local",
        ),
        sa.Column("geometry", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("length_meters", sa.Float, nullable=False, server_default="0"),
        sa.Column("speed_limit", sa.Integer, nullable=True),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("is_one_way", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("lanes", sa.Integer, nullable=False, server_default="2"),
        sa.Column("district_id", postgresql.UUID(as_uuid=True), nullable=True),
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
    op.create_index("ix_road_edges_world_id", "road_edges", ["world_id"])
    op.create_index("ix_road_edges_from_node_id", "road_edges", ["from_node_id"])
    op.create_index("ix_road_edges_to_node_id", "road_edges", ["to_node_id"])
    op.create_index("ix_road_edges_road_class", "road_edges", ["road_class"])
    op.create_index("ix_road_edges_district_id", "road_edges", ["district_id"])


def downgrade() -> None:
    op.drop_table("road_edges")
    op.drop_table("road_nodes")

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS road_class")
    op.execute("DROP TYPE IF EXISTS node_type")
