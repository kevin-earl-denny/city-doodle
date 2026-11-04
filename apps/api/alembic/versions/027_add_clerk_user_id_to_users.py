"""Add clerk_user_id to users; make password_hash nullable

CITY-644: Replace email/password auth with Clerk. Existing users are linked to
their Clerk account (by verified primary email) on first sign-in, which sets
clerk_user_id. Users created through Clerk have no password_hash. The sessions
table is no longer used and will be dropped in a follow-up migration.

Revision ID: 027
Revises: 026
Create Date: 2026-11-03

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "027"
down_revision: str | None = "026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("clerk_user_id", sa.String(255), nullable=True))
    op.create_index("ix_users_clerk_user_id", "users", ["clerk_user_id"], unique=True)
    op.alter_column("users", "password_hash", existing_type=sa.String(255), nullable=True)


def downgrade() -> None:
    # Clerk-only users have no password; give them an unusable placeholder so the
    # NOT NULL constraint can be restored. They cannot sign in with a password.
    op.execute("UPDATE users SET password_hash = '!' WHERE password_hash IS NULL")
    op.alter_column("users", "password_hash", existing_type=sa.String(255), nullable=False)
    op.drop_index("ix_users_clerk_user_id", table_name="users")
    op.drop_column("users", "clerk_user_id")
