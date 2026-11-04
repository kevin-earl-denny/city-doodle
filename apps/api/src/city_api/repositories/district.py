"""District repository - data access for districts."""

import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from city_api.models.district import DISTRICT_TYPE_DEFAULTS
from city_api.models.district import District as DistrictModel
from city_api.repositories import road_network as road_network_repo
from city_api.schemas import District, DistrictCreate, DistrictUpdate

logger = logging.getLogger(__name__)


def _ensure_utc(dt: datetime) -> datetime:
    """Ensure datetime is timezone-aware (UTC)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


async def create_district(db: AsyncSession, district_create: DistrictCreate) -> District:
    """Create a new district."""
    logger.debug(
        f"Creating district: type={district_create.type}, "
        f"type_value={district_create.type.value}, world_id={district_create.world_id}"
    )

    # Apply type defaults if not explicitly set (use .value for string key lookup)
    type_value = district_create.type.value
    defaults = DISTRICT_TYPE_DEFAULTS.get(type_value, {})
    logger.debug(f"Type defaults lookup: type={type_value}, defaults={defaults}")

    density = (
        district_create.density if district_create.density != 1.0 else defaults.get("density", 1.0)
    )
    max_height = (
        district_create.max_height
        if district_create.max_height != 4
        else defaults.get("max_height", 4)
    )

    district = DistrictModel(
        world_id=district_create.world_id,
        type=type_value,  # Pass string value (PostgreSQL expects lowercase)
        name=district_create.name,
        geometry=district_create.geometry,
        density=density,
        max_height=max_height,
        transit_access=district_create.transit_access,
        historic=district_create.historic,
        street_grid=district_create.street_grid,
    )
    logger.debug(f"Created DistrictModel with type={district.type}")

    db.add(district)
    try:
        await db.commit()
        logger.debug(f"District committed: id={district.id}")
    except Exception as e:
        logger.error(f"Failed to commit district: {type(e).__name__}: {e}")
        raise

    await db.refresh(district)
    return _to_schema(district)


async def create_districts_bulk(
    db: AsyncSession, districts: list[DistrictCreate]
) -> list[District]:
    """Create multiple districts at once."""
    models = []
    for d in districts:
        type_value = d.type.value
        defaults = DISTRICT_TYPE_DEFAULTS.get(type_value, {})
        density = d.density if d.density != 1.0 else defaults.get("density", 1.0)
        max_height = d.max_height if d.max_height != 4 else defaults.get("max_height", 4)

        models.append(
            DistrictModel(
                world_id=d.world_id,
                type=type_value,  # Pass string value (PostgreSQL expects lowercase)
                name=d.name,
                geometry=d.geometry,
                density=density,
                max_height=max_height,
                transit_access=d.transit_access,
                historic=d.historic,
                street_grid=d.street_grid,
            )
        )
    db.add_all(models)
    await db.commit()
    for m in models:
        await db.refresh(m)
    return [_to_schema(m) for m in models]


async def get_district(db: AsyncSession, district_id: UUID) -> District | None:
    """Get a district by ID."""
    result = await db.execute(select(DistrictModel).where(DistrictModel.id == district_id))
    district = result.scalar_one_or_none()
    if district is None:
        return None
    return _to_schema(district)


async def list_districts_by_world(
    db: AsyncSession, world_id: UUID, historic_only: bool = False
) -> list[District]:
    """List all districts in a world."""
    query = select(DistrictModel).where(DistrictModel.world_id == world_id)
    if historic_only:
        query = query.where(DistrictModel.historic == True)  # noqa: E712
    result = await db.execute(query)
    districts = result.scalars().all()
    return [_to_schema(d) for d in districts]


async def list_districts_by_type(
    db: AsyncSession, world_id: UUID, district_type: str
) -> list[District]:
    """List districts of a specific type in a world."""
    result = await db.execute(
        select(DistrictModel).where(
            DistrictModel.world_id == world_id, DistrictModel.type == district_type
        )
    )
    districts = result.scalars().all()
    return [_to_schema(d) for d in districts]


async def update_district(
    db: AsyncSession, district_id: UUID, district_update: DistrictUpdate
) -> District | None:
    """Update a district."""
    result = await db.execute(select(DistrictModel).where(DistrictModel.id == district_id))
    district = result.scalar_one_or_none()
    if district is None:
        return None

    if district_update.type is not None:
        new_type_value = district_update.type.value
        type_changed = new_type_value != district.type
        district.type = new_type_value  # Pass string value for PostgreSQL enum

        # CITY-297: When type changes, apply new type's default density/max_height
        # unless the update explicitly provides new values
        if type_changed:
            new_defaults = DISTRICT_TYPE_DEFAULTS.get(new_type_value, {})
            if district_update.density is None:
                district.density = new_defaults.get("density", 1.0)
            if district_update.max_height is None:
                district.max_height = new_defaults.get("max_height", 4)

    if district_update.name is not None:
        district.name = district_update.name
    if district_update.geometry is not None:
        district.geometry = district_update.geometry
    if district_update.density is not None:
        district.density = district_update.density
    if district_update.max_height is not None:
        district.max_height = district_update.max_height
    if district_update.transit_access is not None:
        district.transit_access = district_update.transit_access
    if district_update.historic is not None:
        district.historic = district_update.historic
    if district_update.street_grid is not None:
        district.street_grid = district_update.street_grid

    await db.commit()
    await db.refresh(district)
    return _to_schema(district)


async def delete_district(db: AsyncSession, district_id: UUID) -> bool:
    """Delete a district and clean up associated road edges/nodes (CITY-298)."""
    edges_deleted, nodes_deleted = await road_network_repo.delete_edges_by_district(db, district_id)
    if edges_deleted or nodes_deleted:
        logger.info(
            "CITY-298: Cleaned up %d edges and %d orphaned nodes for district %s",
            edges_deleted,
            nodes_deleted,
            district_id,
        )
    result = await db.execute(delete(DistrictModel).where(DistrictModel.id == district_id))
    await db.commit()
    return result.rowcount > 0


async def clear_districts(db: AsyncSession, world_id: UUID) -> int:
    """Delete all districts in a world. Returns count of deleted districts.

    Also cleans up associated road edges/nodes (CITY-298).
    """
    # Get all district IDs first for cleanup
    district_rows = await db.execute(
        select(DistrictModel.id).where(DistrictModel.world_id == world_id)
    )
    district_ids = [row[0] for row in district_rows]

    for district_id in district_ids:
        await road_network_repo.delete_edges_by_district(db, district_id)

    result = await db.execute(delete(DistrictModel).where(DistrictModel.world_id == world_id))
    await db.commit()
    return result.rowcount


def _to_schema(district: DistrictModel) -> District:
    """Convert SQLAlchemy model to Pydantic schema."""
    return District(
        id=district.id,
        world_id=district.world_id,
        type=district.type,
        name=district.name,
        geometry=district.geometry,
        density=district.density,
        max_height=district.max_height,
        transit_access=district.transit_access,
        historic=district.historic,
        street_grid=district.street_grid,
        created_at=_ensure_utc(district.created_at),
        updated_at=_ensure_utc(district.updated_at),
    )
