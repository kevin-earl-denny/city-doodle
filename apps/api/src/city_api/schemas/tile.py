"""Tile schemas - represents a map tile and its lock state."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class TerrainData(BaseModel):
    """Terrain information for a tile."""

    elevation: list[list[float]] = Field(
        default_factory=list,
        description="2D array of elevation values",
    )
    water_bodies: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Water feature polygons",
    )
    vegetation: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Vegetation area polygons",
    )


class TileFeatures(BaseModel):
    """Features placed on a tile."""

    roads: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Road geometries",
    )
    buildings: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Building footprints",
    )
    pois: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Points of interest",
    )


class TileCreate(BaseModel):
    """Request model for creating a new tile."""

    world_id: UUID
    tx: int = Field(..., description="Tile X coordinate")
    ty: int = Field(..., description="Tile Y coordinate")


class Tile(BaseModel):
    """A map tile within a world."""

    id: UUID
    world_id: UUID
    tx: int = Field(..., description="Tile X coordinate")
    ty: int = Field(..., description="Tile Y coordinate")
    terrain_data: TerrainData = Field(default_factory=TerrainData)
    features: dict[str, Any] = Field(
        default_factory=dict,
        description="Tile features — may be a GeoJSON FeatureCollection from the terrain worker or a TileFeatures dict",
    )
    terrain_status: str = Field(
        default="pending",
        description="Terrain generation status: pending, generating, ready, failed",
    )
    terrain_error: str | None = Field(
        default=None, description="Error message if terrain generation failed"
    )
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TileUpdate(BaseModel):
    """Request model for updating a tile."""

    terrain_data: TerrainData | None = None
    features: dict[str, Any] | None = None


class TileLockCreate(BaseModel):
    """Request model for acquiring a tile lock.

    Note: tile_id comes from the URL path, not the request body.
    """

    duration_seconds: int = Field(
        default=300,
        ge=60,
        le=3600,
        description="Lock duration in seconds (1-60 minutes)",
    )


class TileLock(BaseModel):
    """A lock on a tile for concurrent editing."""

    tile_id: UUID
    user_id: UUID
    locked_at: datetime
    expires_at: datetime

    model_config = {"from_attributes": True}
