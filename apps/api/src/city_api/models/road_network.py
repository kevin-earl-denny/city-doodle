"""Road network graph models - nodes (intersections) and edges (road segments)."""

import uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import ENUM as PGEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from city_api.database import Base, JSONVariant

if TYPE_CHECKING:
    from city_api.models.world import World


class RoadClass(str, Enum):
    """Road classification for styling and routing priority."""

    HIGHWAY = "highway"
    ARTERIAL = "arterial"
    COLLECTOR = "collector"
    LOCAL = "local"
    ALLEY = "alley"
    TRAIL = "trail"


class WaterfrontType(str, Enum):
    """CITY-181: Waterfront road type for roads adjacent to water features."""

    RIVERFRONT_DRIVE = "riverfront_drive"
    BOARDWALK = "boardwalk"


class NodeType(str, Enum):
    """Node types for intersection handling."""

    INTERSECTION = "intersection"
    ENDPOINT = "endpoint"
    ROUNDABOUT = "roundabout"
    INTERCHANGE = "interchange"


class RoadNode(Base):
    """A node in the road network graph (intersection or endpoint)."""

    __tablename__ = "road_nodes"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    world_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("worlds.id", ondelete="CASCADE"), nullable=False
    )
    # Position stored as JSON {x, y}
    position: Mapped[dict] = mapped_column(JSONVariant, nullable=False)
    # Use PostgreSQL native enum with explicit lowercase values
    # create_type=False since the enum is managed by migrations
    node_type: Mapped[str] = mapped_column(
        PGEnum(
            "intersection",
            "endpoint",
            "roundabout",
            "interchange",
            name="node_type",
            create_type=False,
        ),
        nullable=False,
        default="intersection",
    )
    # Optional name for major intersections
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
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
    world: Mapped["World"] = relationship("World", back_populates="road_nodes")
    edges_from: Mapped[list["RoadEdge"]] = relationship(
        "RoadEdge",
        foreign_keys="RoadEdge.from_node_id",
        back_populates="from_node",
        cascade="all, delete-orphan",
    )
    edges_to: Mapped[list["RoadEdge"]] = relationship(
        "RoadEdge",
        foreign_keys="RoadEdge.to_node_id",
        back_populates="to_node",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_road_nodes_world_id", "world_id"),
        # Spatial-like index on position for proximity queries
        # (full PostGIS not needed for this scale)
    )


class RoadEdge(Base):
    """An edge in the road network graph (road segment)."""

    __tablename__ = "road_edges"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    world_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("worlds.id", ondelete="CASCADE"), nullable=False
    )
    from_node_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("road_nodes.id", ondelete="CASCADE"), nullable=False
    )
    to_node_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("road_nodes.id", ondelete="CASCADE"), nullable=False
    )
    # Use PostgreSQL native enum with explicit lowercase values
    # create_type=False since the enum is managed by migrations
    road_class: Mapped[str] = mapped_column(
        PGEnum(
            "highway",
            "arterial",
            "collector",
            "local",
            "alley",
            "trail",
            name="road_class",
            create_type=False,
        ),
        nullable=False,
        default="local",
    )
    # Geometry: array of intermediate points [{x, y}, ...] for curved roads
    geometry: Mapped[list] = mapped_column(JSONVariant, nullable=False, default=list)
    # Calculated length in meters
    length_meters: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # Speed limit in km/h
    speed_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Street name
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # One-way flag
    is_one_way: Mapped[bool] = mapped_column(default=False, nullable=False)
    # Number of lanes
    lanes: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    # District this road belongs to (optional)
    district_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    # CITY-181: Waterfront designation (null = not waterfront)
    waterfront_type: Mapped[str | None] = mapped_column(
        PGEnum(
            "riverfront_drive",
            "boardwalk",
            name="waterfront_type",
            create_type=False,
        ),
        nullable=True,
        default=None,
    )
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
    world: Mapped["World"] = relationship("World", back_populates="road_edges")
    from_node: Mapped["RoadNode"] = relationship(
        "RoadNode", foreign_keys=[from_node_id], back_populates="edges_from"
    )
    to_node: Mapped["RoadNode"] = relationship(
        "RoadNode", foreign_keys=[to_node_id], back_populates="edges_to"
    )

    __table_args__ = (
        Index("ix_road_edges_world_id", "world_id"),
        Index("ix_road_edges_from_node_id", "from_node_id"),
        Index("ix_road_edges_to_node_id", "to_node_id"),
        Index("ix_road_edges_road_class", "road_class"),
        Index("ix_road_edges_district_id", "district_id"),
    )


# Road class defaults for speed and lanes
ROAD_CLASS_DEFAULTS = {
    RoadClass.HIGHWAY: {"speed_limit": 100, "lanes": 4},
    RoadClass.ARTERIAL: {"speed_limit": 60, "lanes": 4},
    RoadClass.COLLECTOR: {"speed_limit": 50, "lanes": 2},
    RoadClass.LOCAL: {"speed_limit": 40, "lanes": 2},
    RoadClass.ALLEY: {"speed_limit": 20, "lanes": 1},
}
