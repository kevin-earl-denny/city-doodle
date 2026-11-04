"""District model for persisting zoning districts."""

import uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Uuid, func
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM
from sqlalchemy.orm import Mapped, mapped_column, relationship

from city_api.database import Base, JSONVariant

if TYPE_CHECKING:
    from city_api.models.city import City
    from city_api.models.transit import TransitStation
    from city_api.models.world import World


class DistrictType(str, Enum):
    """Types of zoning districts.

    These match the frontend district types from the placement palette.
    """

    RESIDENTIAL = "residential"
    DOWNTOWN = "downtown"
    COMMERCIAL = "commercial"
    INDUSTRIAL = "industrial"
    HOSPITAL = "hospital"
    UNIVERSITY = "university"
    K12 = "k12"
    PARK = "park"
    AIRPORT = "airport"


class District(Base):
    """A zoning district in a world."""

    __tablename__ = "districts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    world_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("worlds.id", ondelete="CASCADE"), nullable=False
    )
    # Optional link to a city within this world (SET NULL on city delete)
    city_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("cities.id", ondelete="SET NULL"), nullable=True
    )
    # Use PostgreSQL native enum with explicit lowercase values
    # create_type=False since the enum is managed by migrations
    type: Mapped[str] = mapped_column(
        PG_ENUM(
            "residential",
            "downtown",
            "commercial",
            "industrial",
            "hospital",
            "university",
            "k12",
            "park",
            "airport",
            name="district_type",
            create_type=False,
        ),
        nullable=False,
    )
    # Name for labels
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # GeoJSON geometry for the district boundary
    geometry: Mapped[dict] = mapped_column(JSONVariant, nullable=False)
    # Development properties
    density: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    max_height: Mapped[int] = mapped_column(Integer, nullable=False, default=4)
    transit_access: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Historic preservation flag
    historic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Street grid data (roads, gridAngle, personality) as JSONB
    street_grid: Mapped[dict | None] = mapped_column(JSONVariant, nullable=True)
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    world: Mapped["World"] = relationship("World", back_populates="districts")
    city: Mapped["City | None"] = relationship("City", back_populates="districts")
    transit_stations: Mapped[list["TransitStation"]] = relationship(
        "TransitStation", back_populates="district"
    )

    __table_args__ = (
        Index("ix_districts_world_id", "world_id"),
        Index("ix_districts_type", "type"),
        Index("ix_districts_historic", "historic"),
        Index("ix_districts_city_id", "city_id"),
    )


# Default district properties by type (keyed by string value for easy lookup)
DISTRICT_TYPE_DEFAULTS: dict[str, dict] = {
    "residential": {"density": 3.0, "max_height": 8},
    "downtown": {"density": 7.0, "max_height": 30},
    "commercial": {"density": 5.0, "max_height": 15},
    "industrial": {"density": 2.0, "max_height": 4},
    "hospital": {"density": 2.0, "max_height": 6},
    "university": {"density": 2.5, "max_height": 8},
    "k12": {"density": 1.5, "max_height": 4},
    "park": {"density": 0.1, "max_height": 1},
    "airport": {"density": 0.5, "max_height": 3},
}
