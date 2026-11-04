"""Update district_type enum to match frontend types

Revision ID: 010
Revises: 009
Create Date: 2026-02-05

Changes the district_type enum from backend-centric types to frontend-centric types:
- residential_low, residential_med, residential_high -> residential
- commercial (unchanged)
- industrial (unchanged)
- mixed_use, civic -> downtown, hospital, university, k12
- park (unchanged)
- transit -> airport

"""

from collections.abc import Sequence

from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "010"
down_revision: str = "009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Old enum values
OLD_ENUM_VALUES = [
    "residential_low",
    "residential_med",
    "residential_high",
    "commercial",
    "industrial",
    "mixed_use",
    "park",
    "civic",
    "transit",
]

# New enum values
NEW_ENUM_VALUES = [
    "residential",
    "downtown",
    "commercial",
    "industrial",
    "hospital",
    "university",
    "k12",
    "park",
    "airport",
]

# Mapping from old values to new values
OLD_TO_NEW = {
    "residential_low": "residential",
    "residential_med": "residential",
    "residential_high": "downtown",  # High density residential -> downtown
    "commercial": "commercial",
    "industrial": "industrial",
    "mixed_use": "downtown",  # Mixed use -> downtown
    "park": "park",
    "civic": "hospital",  # Civic -> hospital (most common civic use)
    "transit": "airport",  # Transit -> airport
}

# Mapping from new values back to old values (for downgrade)
NEW_TO_OLD = {
    "residential": "residential_med",
    "downtown": "residential_high",
    "commercial": "commercial",
    "industrial": "industrial",
    "hospital": "civic",
    "university": "civic",
    "k12": "civic",
    "park": "park",
    "airport": "transit",
}


def upgrade() -> None:
    # Step 1: Change column to VARCHAR temporarily
    op.alter_column(
        "districts",
        "type",
        type_=postgresql.VARCHAR(50),
        postgresql_using="type::text",
    )

    # Step 2: Update existing values to new enum values
    for old_val, new_val in OLD_TO_NEW.items():
        op.execute(f"UPDATE districts SET type = '{new_val}' WHERE type = '{old_val}'")

    # Step 3: Drop old enum type
    op.execute("DROP TYPE IF EXISTS district_type")

    # Step 4: Create new enum type
    new_enum = postgresql.ENUM(
        *NEW_ENUM_VALUES,
        name="district_type",
        create_type=False,  # created explicitly below; True would re-CREATE it in create_table (CITY-684)
    )
    new_enum.create(op.get_bind(), checkfirst=True)

    # Step 5: Change column back to enum
    op.alter_column(
        "districts",
        "type",
        type_=new_enum,
        postgresql_using="type::district_type",
    )


def downgrade() -> None:
    # Step 1: Change column to VARCHAR temporarily
    op.alter_column(
        "districts",
        "type",
        type_=postgresql.VARCHAR(50),
        postgresql_using="type::text",
    )

    # Step 2: Update values back to old enum values
    for new_val, old_val in NEW_TO_OLD.items():
        op.execute(f"UPDATE districts SET type = '{old_val}' WHERE type = '{new_val}'")

    # Step 3: Drop new enum type
    op.execute("DROP TYPE IF EXISTS district_type")

    # Step 4: Create old enum type
    old_enum = postgresql.ENUM(
        *OLD_ENUM_VALUES,
        name="district_type",
        create_type=False,  # created explicitly below; True would re-CREATE it in create_table (CITY-684)
    )
    old_enum.create(op.get_bind(), checkfirst=True)

    # Step 5: Change column back to enum
    op.alter_column(
        "districts",
        "type",
        type_=old_enum,
        postgresql_using="type::district_type",
    )
