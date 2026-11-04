"""Add brief_usage daily counter

Global (cross-machine) daily cap on World Brief calls, so Opus spend is
bounded no matter how many API machines are running.

CITY-679: global daily spend cap and kill switch for the World Brief endpoint.

Revision ID: 028
Revises: 026
Create Date: 2026-11-03

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "028"
down_revision: str | None = "026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "brief_usage",
        sa.Column("day", sa.Date(), primary_key=True),
        sa.Column("count", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_table("brief_usage")
