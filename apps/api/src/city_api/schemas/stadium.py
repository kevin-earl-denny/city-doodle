"""Stadium schemas - for sports stadiums with street grid impact."""

from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field

from city_api.schemas.road_network import Point


class StadiumType(str, Enum):
    """Types of stadiums with different sizes and impacts."""

    BASEBALL_STADIUM = "baseball_stadium"
    FOOTBALL_STADIUM = "football_stadium"
    ARENA = "arena"


# Stadium size configuration by type (dimensions in meters)
STADIUM_SIZE_CONFIG: dict[StadiumType, dict] = {
    StadiumType.BASEBALL_STADIUM: {
        "width": 200,  # Width in meters
        "height": 180,  # Height in meters
        "capacity": 40000,  # Seating capacity
        "parking_ratio": 0.3,  # Parking area as ratio of stadium size
        "impact_radius": 400,  # How far the street grid is affected (meters)
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


class StadiumSize(BaseModel):
    """Size parameters for a stadium."""

    width: float = Field(..., description="Width in meters")
    height: float = Field(..., description="Height in meters")


class StadiumPlacement(BaseModel):
    """Stadium placement configuration."""

    stadium_type: StadiumType
    position: Point = Field(..., description="Center position of the stadium")
    rotation: float = Field(
        default=0.0,
        ge=0.0,
        lt=360.0,
        description="Rotation angle in degrees (0-360)",
    )
    # Optional custom size (defaults to type-based size)
    custom_size: StadiumSize | None = None


class ParkingLot(BaseModel):
    """A parking lot generated around a stadium."""

    id: UUID
    stadium_id: UUID
    position: Point
    width: float
    height: float
    capacity: int = Field(..., description="Number of parking spaces")
    orientation: float = Field(default=0.0, description="Orientation toward stadium in degrees")


class ParkingLotConfig(BaseModel):
    """Configuration for parking lot generation."""

    lot_count: int = Field(default=4, ge=1, le=8, description="Number of parking lots to generate")
    min_distance: float = Field(
        default=50.0, description="Minimum distance from stadium edge (meters)"
    )
    max_distance: float = Field(
        default=300.0, description="Maximum distance from stadium edge (meters)"
    )
    spaces_per_seat: float = Field(
        default=0.3, description="Ratio of parking spaces to stadium capacity"
    )


class StreetGridImpact(BaseModel):
    """Description of how a stadium impacts the surrounding street grid."""

    stadium_id: UUID
    impact_radius: float = Field(..., description="Radius of impact in meters from stadium center")
    orientation_strength: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="How strongly streets orient toward stadium (0-1)",
    )
    affected_road_ids: list[UUID] = Field(
        default_factory=list, description="IDs of roads affected by this stadium"
    )


class StadiumCreate(BaseModel):
    """Request model for creating a stadium."""

    world_id: UUID
    stadium_type: StadiumType
    position: Point
    rotation: float = 0.0
    custom_size: StadiumSize | None = None
    parking_config: ParkingLotConfig | None = None
    name: str | None = None


class Stadium(BaseModel):
    """A stadium placed in the world."""

    id: UUID
    world_id: UUID
    stadium_type: StadiumType
    position: Point
    rotation: float
    width: float
    height: float
    capacity: int
    name: str | None = None
    parking_lots: list[ParkingLot] = Field(default_factory=list)
    street_grid_impact: StreetGridImpact | None = None

    model_config = {"from_attributes": True}


class StadiumWithImpact(BaseModel):
    """Stadium with computed street grid impact."""

    stadium: Stadium
    impact: StreetGridImpact
    parking_lots: list[ParkingLot]
