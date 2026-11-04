"""Add districts table

Revision ID: 008
Revises: 007
Create Date: 2026-02-04

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "008"
down_revision: str = "007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create district_type enum
    district_type = postgresql.ENUM(
        "residential_low",
        "residential_med",
        "residential_high",
        "commercial",
        "industrial",
        "mixed_use",
        "park",
        "civic",
        "transit",
        name="district_type",
        create_type=False,  # created explicitly below; True would re-CREATE it in create_table (CITY-684)
    )
    district_type.create(op.get_bind(), checkfirst=True)

    # Create districts table
    op.create_table(
        "districts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "world_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("worlds.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("type", district_type, nullable=False),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("geometry", postgresql.JSONB, nullable=False),
        sa.Column("density", sa.Float, nullable=False, server_default="1.0"),
        sa.Column("max_height", sa.Integer, nullable=False, server_default="4"),
        sa.Column("transit_access", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("historic", sa.Boolean, nullable=False, server_default="false"),
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
    op.create_index("ix_districts_world_id", "districts", ["world_id"])
    op.create_index("ix_districts_type", "districts", ["type"])
    op.create_index("ix_districts_historic", "districts", ["historic"])


def downgrade() -> None:
    op.drop_table("districts")
    op.execute("DROP TYPE IF EXISTS district_type")
