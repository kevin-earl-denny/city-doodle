"""City model for persisting multi-city entities within a world."""

import uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Uuid, func
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM
from sqlalchemy.orm import Mapped, mapped_column, relationship

from city_api.database import Base, JSONVariant

if TYPE_CHECKING:
    from city_api.models.district import District
    from city_api.models.neighborhood import Neighborhood
    from city_api.models.world import World


class CityClassification(str, Enum):
    """Classification of a city within a world.

    - CORE: Major city, primary urban center (max 3 per world)
    - SUBURB: Suburban area connected to a core city
    - TOWN: Independent small town
    """

    CORE = "core"
    SUBURB = "suburb"
    TOWN = "town"


class City(Base):
    """A city within a world.

    Worlds can contain multiple cities with different classifications.
    Core cities are the main urban centers (limited to 3 per world),
    suburbs are connected to cores, and towns are independent.
    """

    __tablename__ = "cities"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    world_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("worlds.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Use PostgreSQL native enum with explicit lowercase values
    # create_type=False since the enum is managed by migrations
    classification: Mapped[str] = mapped_column(
        PG_ENUM(
            "core",
            "suburb",
            "town",
            name="cityclassification",
            create_type=False,
        ),
        nullable=False,
    )
    # GeoJSON polygon for the city boundary
    boundary: Mapped[dict] = mapped_column(JSONVariant, nullable=False)
    # Optional year the city was established
    established: Mapped[int | None] = mapped_column(Integer, nullable=True)
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
    world: Mapped["World"] = relationship("World", back_populates="cities")
    districts: Mapped[list["District"]] = relationship("District", back_populates="city")
    neighborhoods: Mapped[list["Neighborhood"]] = relationship(
        "Neighborhood", back_populates="city"
    )

    __table_args__ = (
        Index("ix_cities_world_id", "world_id"),
        Index("ix_cities_classification", "classification"),
    )
