"""POI (Point of Interest) model for persisting POIs."""

import uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Index, String, Uuid, func
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM
from sqlalchemy.orm import Mapped, mapped_column, relationship

from city_api.database import Base, JSONVariant

if TYPE_CHECKING:
    from city_api.models.world import World


class POIType(str, Enum):
    """Types of Points of Interest.

    These match the frontend POI types.
    """

    HOSPITAL = "hospital"
    SCHOOL = "school"
    UNIVERSITY = "university"
    PARK = "park"
    TRANSIT = "transit"
    SHOPPING = "shopping"
    CIVIC = "civic"
    INDUSTRIAL = "industrial"


class POI(Base):
    """A Point of Interest in a world."""

    __tablename__ = "pois"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    world_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("worlds.id", ondelete="CASCADE"), nullable=False
    )
    # Use PostgreSQL native enum with explicit lowercase values
    # create_type=False since the enum is managed by migrations
    type: Mapped[str] = mapped_column(
        PG_ENUM(
            "hospital",
            "school",
            "university",
            "park",
            "transit",
            "shopping",
            "civic",
            "industrial",
            name="poi_type",
            create_type=False,
        ),
        nullable=False,
    )
    # Name for labels
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Position coordinates
    position_x: Mapped[float] = mapped_column(Float, nullable=False)
    position_y: Mapped[float] = mapped_column(Float, nullable=False)
    # Optional polygon footprint for campus/compound POIs (CITY-440)
    footprint: Mapped[list | None] = mapped_column(JSONVariant, nullable=True)
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
    world: Mapped["World"] = relationship("World", back_populates="pois")

    __table_args__ = (
        Index("ix_pois_world_id", "world_id"),
        Index("ix_pois_type", "type"),
    )
