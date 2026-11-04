"""PlacedSeed schemas - for placed seeds on the world map."""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class Position(BaseModel):
    """Position coordinates on the map."""

    x: float
    y: float


class ParkSize(str, Enum):
    """Park size presets from pocket parks to large city parks."""

    POCKET = "pocket"  # 0.1-0.5 acres
    NEIGHBORHOOD = "neighborhood"  # 1-5 acres
    COMMUNITY = "community"  # 10-50 acres
    REGIONAL = "regional"  # 50-200 acres
    CITY = "city"  # 200+ acres


class ParkMetadata(BaseModel):
    """Metadata specific to park seeds."""

    size: ParkSize = Field(default=ParkSize.NEIGHBORHOOD, description="Park size preset")
    name: str | None = Field(
        default=None, description="Custom park name (auto-generated if not provided)"
    )
    has_pond: bool = Field(default=False, description="Whether the park has a pond feature")
    has_trails: bool = Field(default=True, description="Whether the park has internal trails")
    connected_road_id: str | None = Field(
        default=None, description="ID of the road this park connects to"
    )


class PlacedSeedCreate(BaseModel):
    """Request model for creating a placed seed."""

    seed_type_id: str = Field(..., min_length=1, max_length=50, description="ID of the seed type")
    position: Position = Field(..., description="Position where the seed is placed")
    metadata: dict[str, Any] | None = Field(
        default=None,
        description="Optional metadata (e.g., park size, features)",
    )


class PlacedSeedBulkCreate(BaseModel):
    """Request model for bulk creating placed seeds."""

    seeds: list[PlacedSeedCreate] = Field(..., description="List of seeds to create")


class PlacedSeed(BaseModel):
    """A seed that has been placed on the world map."""

    id: UUID
    world_id: UUID
    seed_type_id: str
    position: Position
    placed_at: datetime
    metadata: dict[str, Any] | None = Field(
        default=None,
        description="Optional metadata (e.g., park size, features)",
    )

    model_config = {"from_attributes": True}
