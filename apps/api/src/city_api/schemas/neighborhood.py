"""Neighborhood schemas - represents named areas in a world."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class NeighborhoodCreate(BaseModel):
    """Request model for creating a new neighborhood."""

    world_id: UUID
    city_id: UUID | None = None
    name: str = Field(
        ..., min_length=1, max_length=255, description="Display name for the neighborhood"
    )
    geometry: dict[str, Any] = Field(
        ...,
        description="GeoJSON geometry for the neighborhood boundary (Polygon)",
    )
    label_color: str | None = Field(
        default=None,
        pattern=r"^#[0-9A-Fa-f]{6}$",
        description="Hex color for the label",
    )
    accent_color: str | None = Field(
        default=None,
        pattern=r"^#[0-9A-Fa-f]{6}$",
        description="Hex color for optional tint",
    )


class NeighborhoodUpdate(BaseModel):
    """Request model for updating a neighborhood."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    city_id: UUID | None = None
    geometry: dict[str, Any] | None = None
    label_color: str | None = Field(
        default=None,
        pattern=r"^#[0-9A-Fa-f]{6}$",
    )
    accent_color: str | None = Field(
        default=None,
        pattern=r"^#[0-9A-Fa-f]{6}$",
    )


class Neighborhood(BaseModel):
    """A named neighborhood area in a world."""

    id: UUID
    world_id: UUID
    city_id: UUID | None = None
    name: str
    geometry: dict[str, Any] = Field(
        ...,
        description="GeoJSON geometry for the neighborhood boundary",
    )
    label_color: str | None = None
    accent_color: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class NeighborhoodBulkCreate(BaseModel):
    """Request model for creating multiple neighborhoods."""

    neighborhoods: list[NeighborhoodCreate]
