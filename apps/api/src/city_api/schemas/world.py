"""World schema - represents a user's city map."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

GeographicSetting = Literal[
    "coastal",
    "bay_harbor",
    "river_valley",
    "lakefront",
    "inland",
    "island",
    "peninsula",
    "delta",
]


class WorldSettings(BaseModel):
    """Configuration settings for a world."""

    geographic_setting: GeographicSetting = Field(
        default="coastal",
        description="Geographic setting determining water body layout",
    )
    grid_organic: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="0 = strict grid, 1 = fully organic street layout",
    )
    sprawl_compact: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="0 = sprawling suburbs, 1 = dense urban core",
    )
    historic_modern: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="0 = historic preservation focus, 1 = modern redevelopment",
    )
    transit_car: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="0 = transit-oriented, 1 = car-dependent",
    )
    block_size_meters: int = Field(
        default=150,
        ge=50,
        le=300,
        description="Size of a city block in meters (50-300)",
    )
    district_size_meters: int = Field(
        default=3200,
        ge=1000,
        le=6000,
        description="Size of a district in meters (1000-6000, default ~2 miles for ~4 sq mi districts)",
    )
    beach_enabled: bool = Field(
        default=True,
        description="Whether to generate beaches along coastlines",
    )
    beach_width_multiplier: float = Field(
        default=1.0,
        ge=0.5,
        le=2.0,
        description="Multiplier for beach width (0.5 = narrow, 2.0 = wide)",
    )
    # Terrain hints from the World Brief (CITY-659). None = let the seed decide.
    # Angles use the engine's mask convention: 0 = east, 90 = south (screen +y).
    water_direction_deg: float | None = Field(
        default=None,
        ge=0.0,
        lt=360.0,
        description="Direction of open water from the city centre (0=E, 90=S, 180=W, 270=N)",
    )
    river_axis_deg: float | None = Field(
        default=None,
        ge=0.0,
        lt=180.0,
        description="Undirected river axis for river valleys (0=E-W, 90=N-S)",
    )
    relief: Literal["flat", "rolling", "hilly", "mountainous"] | None = Field(
        default=None,
        description="Overall terrain roughness",
    )


class WorldCreate(BaseModel):
    """Request model for creating a new world."""

    name: str = Field(..., min_length=1, max_length=100)
    seed: int | None = Field(default=None, description="Random seed for generation")
    settings: WorldSettings = Field(default_factory=WorldSettings)


class WorldUpdate(BaseModel):
    """Request model for updating a world."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    settings: WorldSettings | None = Field(default=None)


class World(BaseModel):
    """A world (city map) owned by a user."""

    id: UUID
    user_id: UUID
    name: str
    seed: int
    settings: WorldSettings
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
