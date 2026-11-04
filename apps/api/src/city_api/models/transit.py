"""Transit models - stations, lines, and line segments."""

import uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM
from sqlalchemy.orm import Mapped, mapped_column, relationship

from city_api.database import Base, JSONVariant

if TYPE_CHECKING:
    from city_api.models.district import District
    from city_api.models.world import World


class StationType(str, Enum):
    """Types of transit stations."""

    SUBWAY = "subway"
    RAIL = "rail"


class LineType(str, Enum):
    """Types of transit lines."""

    SUBWAY = "subway"
    RAIL = "rail"


class TransitStation(Base):
    """A transit station (subway or rail) in a world."""

    __tablename__ = "transit_stations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    world_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("worlds.id", ondelete="CASCADE"), nullable=False
    )
    district_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("districts.id", ondelete="SET NULL"), nullable=True
    )
    station_type: Mapped[str] = mapped_column(
        PG_ENUM(
            "subway",
            "rail",
            name="station_type",
            create_type=False,
        ),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    position_x: Mapped[float] = mapped_column(Float, nullable=False)
    position_y: Mapped[float] = mapped_column(Float, nullable=False)
    is_terminus: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
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
    world: Mapped["World"] = relationship("World", back_populates="transit_stations")
    district: Mapped["District"] = relationship("District", back_populates="transit_stations")
    segments_from: Mapped[list["TransitLineSegment"]] = relationship(
        "TransitLineSegment",
        foreign_keys="TransitLineSegment.from_station_id",
        back_populates="from_station",
        cascade="all, delete-orphan",
    )
    segments_to: Mapped[list["TransitLineSegment"]] = relationship(
        "TransitLineSegment",
        foreign_keys="TransitLineSegment.to_station_id",
        back_populates="to_station",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_transit_stations_world_id", "world_id"),
        Index("ix_transit_stations_district_id", "district_id"),
        Index("ix_transit_stations_station_type", "station_type"),
    )


class TransitLine(Base):
    """A transit line (subway or rail route) in a world."""

    __tablename__ = "transit_lines"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    world_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("worlds.id", ondelete="CASCADE"), nullable=False
    )
    line_type: Mapped[str] = mapped_column(
        PG_ENUM(
            "subway",
            "rail",
            name="line_type",
            create_type=False,
        ),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    color: Mapped[str] = mapped_column(String(7), nullable=False, default="#FF0000")
    is_auto_generated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
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
    world: Mapped["World"] = relationship("World", back_populates="transit_lines")
    segments: Mapped[list["TransitLineSegment"]] = relationship(
        "TransitLineSegment",
        back_populates="line",
        cascade="all, delete-orphan",
        order_by="TransitLineSegment.order_in_line",
    )

    __table_args__ = (
        Index("ix_transit_lines_world_id", "world_id"),
        Index("ix_transit_lines_line_type", "line_type"),
        UniqueConstraint("world_id", "name", name="uq_transit_line_world_name"),
    )


class TransitLineSegment(Base):
    """A segment of a transit line connecting two stations."""

    __tablename__ = "transit_line_segments"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    line_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("transit_lines.id", ondelete="CASCADE"), nullable=False
    )
    from_station_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("transit_stations.id", ondelete="CASCADE"), nullable=False
    )
    to_station_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("transit_stations.id", ondelete="CASCADE"), nullable=False
    )
    # Geometry: array of intermediate points [{x, y}, ...] for curved segments
    geometry: Mapped[list] = mapped_column(JSONVariant, nullable=False, default=list)
    is_underground: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    order_in_line: Mapped[int] = mapped_column(Integer, nullable=False)
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
    line: Mapped["TransitLine"] = relationship("TransitLine", back_populates="segments")
    from_station: Mapped["TransitStation"] = relationship(
        "TransitStation", foreign_keys=[from_station_id], back_populates="segments_from"
    )
    to_station: Mapped["TransitStation"] = relationship(
        "TransitStation", foreign_keys=[to_station_id], back_populates="segments_to"
    )

    __table_args__ = (
        Index("ix_transit_line_segments_line_id", "line_id"),
        Index("ix_transit_line_segments_from_station_id", "from_station_id"),
        Index("ix_transit_line_segments_to_station_id", "to_station_id"),
        Index("ix_transit_line_segments_order", "line_id", "order_in_line"),
        UniqueConstraint(
            "line_id", "from_station_id", "to_station_id", name="uq_segment_line_stations"
        ),
        CheckConstraint("from_station_id != to_station_id", name="ck_segment_no_self_ref"),
    )
