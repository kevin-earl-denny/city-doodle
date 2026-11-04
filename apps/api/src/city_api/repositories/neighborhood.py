"""Neighborhood repository - data access for neighborhoods."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from city_api.models.neighborhood import Neighborhood as NeighborhoodModel
from city_api.schemas.neighborhood import Neighborhood, NeighborhoodCreate, NeighborhoodUpdate


def _ensure_utc(dt: datetime) -> datetime:
    """Ensure datetime is timezone-aware (UTC)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


async def create_neighborhood(
    db: AsyncSession, neighborhood_create: NeighborhoodCreate
) -> Neighborhood:
    """Create a new neighborhood."""
    neighborhood = NeighborhoodModel(
        world_id=neighborhood_create.world_id,
        name=neighborhood_create.name,
        geometry=neighborhood_create.geometry,
        label_color=neighborhood_create.label_color,
        accent_color=neighborhood_create.accent_color,
    )
    db.add(neighborhood)
    await db.commit()
    await db.refresh(neighborhood)
    return _to_schema(neighborhood)


async def create_neighborhoods_bulk(
    db: AsyncSession, neighborhoods: list[NeighborhoodCreate]
) -> list[Neighborhood]:
    """Create multiple neighborhoods at once."""
    models = []
    for n in neighborhoods:
        models.append(
            NeighborhoodModel(
                world_id=n.world_id,
                name=n.name,
                geometry=n.geometry,
                label_color=n.label_color,
                accent_color=n.accent_color,
            )
        )
    db.add_all(models)
    await db.commit()
    for m in models:
        await db.refresh(m)
    return [_to_schema(m) for m in models]


async def get_neighborhood(db: AsyncSession, neighborhood_id: UUID) -> Neighborhood | None:
    """Get a neighborhood by ID."""
    result = await db.execute(
        select(NeighborhoodModel).where(NeighborhoodModel.id == neighborhood_id)
    )
    neighborhood = result.scalar_one_or_none()
    if neighborhood is None:
        return None
    return _to_schema(neighborhood)


async def list_neighborhoods_by_world(db: AsyncSession, world_id: UUID) -> list[Neighborhood]:
    """List all neighborhoods in a world."""
    result = await db.execute(
        select(NeighborhoodModel).where(NeighborhoodModel.world_id == world_id)
    )
    neighborhoods = result.scalars().all()
    return [_to_schema(n) for n in neighborhoods]


async def update_neighborhood(
    db: AsyncSession, neighborhood_id: UUID, neighborhood_update: NeighborhoodUpdate
) -> Neighborhood | None:
    """Update a neighborhood."""
    result = await db.execute(
        select(NeighborhoodModel).where(NeighborhoodModel.id == neighborhood_id)
    )
    neighborhood = result.scalar_one_or_none()
    if neighborhood is None:
        return None

    if neighborhood_update.name is not None:
        neighborhood.name = neighborhood_update.name
    if neighborhood_update.geometry is not None:
        neighborhood.geometry = neighborhood_update.geometry
    if neighborhood_update.label_color is not None:
        neighborhood.label_color = neighborhood_update.label_color
    if neighborhood_update.accent_color is not None:
        neighborhood.accent_color = neighborhood_update.accent_color

    await db.commit()
    await db.refresh(neighborhood)
    return _to_schema(neighborhood)


async def delete_neighborhood(db: AsyncSession, neighborhood_id: UUID) -> bool:
    """Delete a neighborhood."""
    result = await db.execute(
        select(NeighborhoodModel).where(NeighborhoodModel.id == neighborhood_id)
    )
    neighborhood = result.scalar_one_or_none()
    if neighborhood is None:
        return False

    await db.delete(neighborhood)
    await db.commit()
    return True


async def clear_neighborhoods(db: AsyncSession, world_id: UUID) -> None:
    """Delete all neighborhoods in a world."""
    result = await db.execute(
        select(NeighborhoodModel).where(NeighborhoodModel.world_id == world_id)
    )
    neighborhoods = result.scalars().all()
    for neighborhood in neighborhoods:
        await db.delete(neighborhood)
    await db.commit()


def _to_schema(neighborhood: NeighborhoodModel) -> Neighborhood:
    """Convert SQLAlchemy model to Pydantic schema."""
    return Neighborhood(
        id=neighborhood.id,
        world_id=neighborhood.world_id,
        name=neighborhood.name,
        geometry=neighborhood.geometry,
        label_color=neighborhood.label_color,
        accent_color=neighborhood.accent_color,
        created_at=_ensure_utc(neighborhood.created_at),
        updated_at=_ensure_utc(neighborhood.updated_at),
    )
