"""Add waterfront_type column to road_edges

Creates the waterfront_type enum ('riverfront_drive', 'boardwalk') and adds
a nullable waterfront_type column to road_edges for CITY-181 waterfront
road designation.

CITY-611: Fix 503 on GET /worlds/{id}/road-network caused by missing column.

Revision ID: 025
Revises: 024
Create Date: 2026-02-22

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "025"
down_revision: str | None = "024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    waterfront_type = postgresql.ENUM(
        "riverfront_drive",
        "boardwalk",
        name="waterfront_type",
        create_type=False,  # created explicitly below; True would re-CREATE it in create_table (CITY-684)
    )
    waterfront_type.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "road_edges",
        sa.Column(
            "waterfront_type",
            waterfront_type,
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("road_edges", "waterfront_type")
    op.execute("DROP TYPE IF EXISTS waterfront_type")
