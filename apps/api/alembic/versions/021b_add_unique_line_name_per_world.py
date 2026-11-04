"""Add unique constraint on transit line name per world

Prevents duplicate transit line names within the same world.
Deduplicates existing rows by appending a numeric suffix before
adding the constraint.

Revision ID: 021b
Revises: 021
Create Date: 2026-02-08

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "021b"
down_revision: str | None = "021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Deduplicate existing transit line names within the same world.
    # For each set of duplicates, keep the oldest row unchanged and
    # append " (2)", " (3)", etc. to the rest, ordered by created_at.
    conn = op.get_bind()
    dupes = conn.execute(
        sa.text(
            """
            SELECT world_id, name
            FROM transit_lines
            GROUP BY world_id, name
            HAVING count(*) > 1
            """
        )
    ).fetchall()

    for world_id, name in dupes:
        rows = conn.execute(
            sa.text(
                """
                SELECT id FROM transit_lines
                WHERE world_id = :wid AND name = :name
                ORDER BY created_at
                """
            ),
            {"wid": world_id, "name": name},
        ).fetchall()
        # Skip the first (oldest) row, rename the rest
        for idx, row in enumerate(rows[1:], start=2):
            conn.execute(
                sa.text("UPDATE transit_lines SET name = :new_name WHERE id = :id"),
                {"new_name": f"{name} ({idx})", "id": row[0]},
            )

    op.create_unique_constraint(
        "uq_transit_line_world_name",
        "transit_lines",
        ["world_id", "name"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_transit_line_world_name", "transit_lines", type_="unique")
