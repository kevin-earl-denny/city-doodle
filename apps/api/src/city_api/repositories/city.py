"""City repository - data access for cities."""

import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from city_api.models.city import City as CityModel
from city_api.schemas.city import CityCreate, CityResponse, CityUpdate

logger = logging.getLogger(__name__)


def _ensure_utc(dt: datetime) -> datetime:
    """Ensure datetime is timezone-aware (UTC)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


async def list_cities_by_world(db: AsyncSession, world_id: UUID) -> list[CityResponse]:
    """List all cities in a world."""
    result = await db.execute(select(CityModel).where(CityModel.world_id == world_id))
    cities = result.scalars().all()
    return [_to_schema(c) for c in cities]


async def get_city(db: AsyncSession, city_id: UUID) -> CityResponse | None:
    """Get a city by ID."""
    result = await db.execute(select(CityModel).where(CityModel.id == city_id))
    city = result.scalar_one_or_none()
    if city is None:
        return None
    return _to_schema(city)


async def count_by_classification(db: AsyncSession, world_id: UUID, classification: str) -> int:
    """Count cities of a specific classification in a world."""
    result = await db.execute(
        select(func.count())
        .select_from(CityModel)
        .where(
            CityModel.world_id == world_id,
            CityModel.classification == classification,
        )
    )
    return result.scalar_one()


async def create_city(db: AsyncSession, city_create: CityCreate) -> CityResponse:
    """Create a new city.

    Enforces a maximum of 3 core cities per world.
    """
    # Enforce max 3 core cities per world
    if city_create.classification == "core":
        core_count = await count_by_classification(db, city_create.world_id, "core")
        if core_count >= 3:
            raise ValueError("Maximum of 3 core cities per world")

    city = CityModel(
        world_id=city_create.world_id,
        name=city_create.name,
        classification=city_create.classification.value,
        boundary=city_create.boundary,
        established=city_create.established,
    )
    db.add(city)
    await db.commit()
    await db.refresh(city)
    return _to_schema(city)


async def update_city(
    db: AsyncSession, city_id: UUID, city_update: CityUpdate
) -> CityResponse | None:
    """Update a city."""
    result = await db.execute(select(CityModel).where(CityModel.id == city_id))
    city = result.scalar_one_or_none()
    if city is None:
        return None

    # If changing to core, enforce max 3 core cities per world
    if (
        city_update.classification is not None
        and city_update.classification.value != city.classification
    ):
        if city_update.classification == "core":
            core_count = await count_by_classification(db, city.world_id, "core")
            if core_count >= 3:
                raise ValueError("Maximum of 3 core cities per world")
        city.classification = city_update.classification.value

    if city_update.name is not None:
        city.name = city_update.name
    if city_update.boundary is not None:
        city.boundary = city_update.boundary
    if city_update.established is not None:
        city.established = city_update.established

    await db.commit()
    await db.refresh(city)
    return _to_schema(city)


async def delete_city(db: AsyncSession, city_id: UUID) -> bool:
    """Delete a city.

    Cascade: neighborhoods are deleted, districts are unlinked (SET NULL).
    """
    result = await db.execute(select(CityModel).where(CityModel.id == city_id))
    city = result.scalar_one_or_none()
    if city is None:
        return False

    await db.delete(city)
    await db.commit()
    return True


def _to_schema(city: CityModel) -> CityResponse:
    """Convert SQLAlchemy model to Pydantic schema."""
    return CityResponse(
        id=city.id,
        world_id=city.world_id,
        name=city.name,
        classification=city.classification,
        boundary=city.boundary,
        established=city.established,
        created_at=_ensure_utc(city.created_at),
        updated_at=_ensure_utc(city.updated_at),
    )
