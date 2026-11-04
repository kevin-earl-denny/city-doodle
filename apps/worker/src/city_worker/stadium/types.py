"""Types for stadium-related generation."""

from dataclasses import dataclass, field
from enum import Enum
from typing import NamedTuple
from uuid import UUID


class StadiumType(str, Enum):
    """Types of stadiums."""

    BASEBALL_STADIUM = "baseball_stadium"
    FOOTBALL_STADIUM = "football_stadium"
    ARENA = "arena"


class Point(NamedTuple):
    """A 2D point."""

    x: float
    y: float


# Stadium size configuration by type
STADIUM_SIZE_CONFIG: dict[StadiumType, dict] = {
    StadiumType.BASEBALL_STADIUM: {
        "width": 200,
        "height": 180,
        "capacity": 40000,
        "parking_ratio": 0.3,
        "impact_radius": 400,
    },
    StadiumType.FOOTBALL_STADIUM: {
        "width": 250,
        "height": 180,
        "capacity": 70000,
        "parking_ratio": 0.35,
        "impact_radius": 500,
    },
    StadiumType.ARENA: {
        "width": 120,
        "height": 100,
        "capacity": 20000,
        "parking_ratio": 0.25,
        "impact_radius": 300,
    },
}


@dataclass
class StadiumConfig:
    """Configuration for a stadium."""

    stadium_type: StadiumType
    width: float
    height: float
    capacity: int
    parking_ratio: float
    impact_radius: float

    @classmethod
    def from_type(cls, stadium_type: StadiumType) -> "StadiumConfig":
        """Create config from stadium type using defaults."""
        config = STADIUM_SIZE_CONFIG[stadium_type]
        return cls(
            stadium_type=stadium_type,
            width=config["width"],
            height=config["height"],
            capacity=config["capacity"],
            parking_ratio=config["parking_ratio"],
            impact_radius=config["impact_radius"],
        )


@dataclass
class StadiumPlacement:
    """A stadium placement in the world."""

    stadium_id: UUID
    config: StadiumConfig
    position: Point
    rotation: float = 0.0  # degrees

    @property
    def center(self) -> Point:
        """Get the center position of the stadium."""
        return self.position

    def get_corners(self) -> list[Point]:
        """Get the four corners of the stadium bounding box.

        Returns corners in order: top-left, top-right, bottom-right, bottom-left.
        Accounts for rotation.
        """
        import math

        half_w = self.config.width / 2
        half_h = self.config.height / 2
        rad = math.radians(self.rotation)
        cos_r = math.cos(rad)
        sin_r = math.sin(rad)

        # Local corners (unrotated)
        local_corners = [
            (-half_w, -half_h),  # top-left
            (half_w, -half_h),  # top-right
            (half_w, half_h),  # bottom-right
            (-half_w, half_h),  # bottom-left
        ]

        # Rotate and translate to world coordinates
        corners = []
        for lx, ly in local_corners:
            wx = self.position.x + (lx * cos_r - ly * sin_r)
            wy = self.position.y + (lx * sin_r + ly * cos_r)
            corners.append(Point(wx, wy))

        return corners


@dataclass
class ParkingLotResult:
    """Result of parking lot generation."""

    lot_id: UUID
    stadium_id: UUID
    position: Point
    width: float
    height: float
    capacity: int
    orientation: float  # degrees, pointing toward stadium


@dataclass
class StreetOrientationResult:
    """Result of street orientation calculation."""

    road_id: UUID
    original_geometry: list[Point]
    adjusted_geometry: list[Point]
    orientation_strength: float  # 0-1, how strongly it was pulled toward stadium


@dataclass
class StreetGridImpactResult:
    """Complete result of stadium street grid impact calculation."""

    stadium_id: UUID
    impact_radius: float
    affected_roads: list[StreetOrientationResult] = field(default_factory=list)
    new_roads: list[dict] = field(default_factory=list)  # Roads created toward stadium
