"""POI repository - data access for Points of Interest."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from city_api.models import poi as poi_models
from city_api.schemas.poi import POI, POICreate, POIUpdate


def _ensure_utc(dt: datetime) -> datetime:
    """Ensure datetime is timezone-aware (UTC)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


async def create_poi(db: AsyncSession, poi_create: POICreate) -> POI:
    """Create a new POI."""
    poi = poi_models.POI(
        world_id=poi_create.world_id,
        type=poi_create.type.value,
        name=poi_create.name,
        position_x=poi_create.position_x,
        position_y=poi_create.position_y,
        footprint=poi_create.footprint,
    )
    db.add(poi)
    await db.commit()
    await db.refresh(poi)
    return _to_schema(poi)


async def create_pois_bulk(db: AsyncSession, pois: list[POICreate]) -> list[POI]:
    """Create multiple POIs at once."""
    models = []
    for p in pois:
        models.append(
            poi_models.POI(
                world_id=p.world_id,
                type=p.type.value,
                name=p.name,
                position_x=p.position_x,
                position_y=p.position_y,
                footprint=p.footprint,
            )
        )
    db.add_all(models)
    await db.commit()
    for m in models:
        await db.refresh(m)
    return [_to_schema(m) for m in models]


async def get_poi(db: AsyncSession, poi_id: UUID) -> POI | None:
    """Get a POI by ID."""
    result = await db.execute(select(poi_models.POI).where(poi_models.POI.id == poi_id))
    poi = result.scalar_one_or_none()
    if poi is None:
        return None
    return _to_schema(poi)


async def list_pois_by_world(
    db: AsyncSession,
    world_id: UUID,
    poi_type: str | None = None,
) -> list[POI]:
    """List all POIs in a world, optionally filtered by type."""
    query = select(poi_models.POI).where(poi_models.POI.world_id == world_id)
    if poi_type is not None:
        query = query.where(poi_models.POI.type == poi_type)
    result = await db.execute(query)
    pois = result.scalars().all()
    return [_to_schema(p) for p in pois]


async def update_poi(db: AsyncSession, poi_id: UUID, poi_update: POIUpdate) -> POI | None:
    """Update a POI."""
    result = await db.execute(select(poi_models.POI).where(poi_models.POI.id == poi_id))
    poi = result.scalar_one_or_none()
    if poi is None:
        return None

    if poi_update.type is not None:
        poi.type = poi_update.type.value
    if poi_update.name is not None:
        poi.name = poi_update.name
    if poi_update.position_x is not None:
        poi.position_x = poi_update.position_x
    if poi_update.position_y is not None:
        poi.position_y = poi_update.position_y
    if poi_update.footprint is not None:
        poi.footprint = poi_update.footprint

    await db.commit()
    await db.refresh(poi)
    return _to_schema(poi)


async def delete_poi(db: AsyncSession, poi_id: UUID) -> bool:
    """Delete a POI."""
    result = await db.execute(select(poi_models.POI).where(poi_models.POI.id == poi_id))
    poi = result.scalar_one_or_none()
    if poi is None:
        return False

    await db.delete(poi)
    await db.commit()
    return True


async def clear_pois(db: AsyncSession, world_id: UUID) -> None:
    """Delete all POIs in a world."""
    await db.execute(delete(poi_models.POI).where(poi_models.POI.world_id == world_id))
    await db.commit()


def _to_schema(poi: poi_models.POI) -> POI:
    """Convert SQLAlchemy model to Pydantic schema."""
    return POI(
        id=poi.id,
        world_id=poi.world_id,
        type=poi.type,
        name=poi.name,
        position_x=poi.position_x,
        position_y=poi.position_y,
        footprint=poi.footprint,
        created_at=_ensure_utc(poi.created_at),
        updated_at=_ensure_utc(poi.updated_at),
    )
