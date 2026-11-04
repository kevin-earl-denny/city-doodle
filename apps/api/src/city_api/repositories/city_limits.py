"""CityLimits repository - data access for city boundaries."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from city_api.models.city_limits import CityLimits as CityLimitsModel
from city_api.schemas.city_limits import CityLimits, CityLimitsCreate, CityLimitsUpdate


def _ensure_utc(dt: datetime) -> datetime:
    """Ensure datetime is timezone-aware (UTC)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


async def get_by_world(db: AsyncSession, world_id: UUID) -> CityLimits | None:
    """Get the city limits for a world (there's at most one)."""
    result = await db.execute(select(CityLimitsModel).where(CityLimitsModel.world_id == world_id))
    city_limits = result.scalar_one_or_none()
    if city_limits is None:
        return None
    return _to_schema(city_limits)


async def upsert(db: AsyncSession, data: CityLimitsCreate) -> CityLimits:
    """Create or replace the city limits for a world."""
    # Check if one already exists
    result = await db.execute(
        select(CityLimitsModel).where(CityLimitsModel.world_id == data.world_id)
    )
    existing = result.scalar_one_or_none()

    if existing:
        existing.name = data.name
        existing.boundary = data.boundary
        existing.established = data.established
        await db.commit()
        await db.refresh(existing)
        return _to_schema(existing)
    else:
        city_limits = CityLimitsModel(
            world_id=data.world_id,
            name=data.name,
            boundary=data.boundary,
            established=data.established,
        )
        db.add(city_limits)
        await db.commit()
        await db.refresh(city_limits)
        return _to_schema(city_limits)


async def update(db: AsyncSession, world_id: UUID, data: CityLimitsUpdate) -> CityLimits | None:
    """Update the city limits for a world."""
    result = await db.execute(select(CityLimitsModel).where(CityLimitsModel.world_id == world_id))
    city_limits = result.scalar_one_or_none()
    if city_limits is None:
        return None

    if data.name is not None:
        city_limits.name = data.name
    if data.boundary is not None:
        city_limits.boundary = data.boundary
    if data.established is not None:
        city_limits.established = data.established

    await db.commit()
    await db.refresh(city_limits)
    return _to_schema(city_limits)


async def delete_by_world(db: AsyncSession, world_id: UUID) -> bool:
    """Delete the city limits for a world."""
    result = await db.execute(delete(CityLimitsModel).where(CityLimitsModel.world_id == world_id))
    await db.commit()
    return result.rowcount > 0


def _to_schema(city_limits: CityLimitsModel) -> CityLimits:
    """Convert SQLAlchemy model to Pydantic schema."""
    return CityLimits(
        id=city_limits.id,
        world_id=city_limits.world_id,
        name=city_limits.name,
        boundary=city_limits.boundary,
        established=city_limits.established,
        created_at=_ensure_utc(city_limits.created_at),
        updated_at=_ensure_utc(city_limits.updated_at),
    )
