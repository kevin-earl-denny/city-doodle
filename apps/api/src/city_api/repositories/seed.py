"""PlacedSeed repository - data access for placed seeds."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from city_api.models import PlacedSeed as PlacedSeedModel
from city_api.schemas import PlacedSeed, PlacedSeedCreate, Position


def _ensure_utc(dt: datetime) -> datetime:
    """Ensure datetime is timezone-aware (UTC). SQLite returns naive datetimes."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


async def create_seed(
    db: AsyncSession, world_id: UUID, seed_create: PlacedSeedCreate
) -> PlacedSeed:
    """Create a new placed seed."""
    seed = PlacedSeedModel(
        world_id=world_id,
        seed_type_id=seed_create.seed_type_id,
        position_x=seed_create.position.x,
        position_y=seed_create.position.y,
        seed_metadata=seed_create.metadata,
    )
    db.add(seed)
    await db.commit()
    await db.refresh(seed)
    return _to_schema(seed)


async def create_seeds_bulk(
    db: AsyncSession, world_id: UUID, seeds: list[PlacedSeedCreate]
) -> list[PlacedSeed]:
    """Create multiple placed seeds in a single transaction."""
    seed_models = [
        PlacedSeedModel(
            world_id=world_id,
            seed_type_id=seed.seed_type_id,
            position_x=seed.position.x,
            position_y=seed.position.y,
            seed_metadata=seed.metadata,
        )
        for seed in seeds
    ]
    db.add_all(seed_models)
    await db.commit()
    # Refresh all to get generated IDs and timestamps
    for seed_model in seed_models:
        await db.refresh(seed_model)
    return [_to_schema(s) for s in seed_models]


async def get_seed(db: AsyncSession, seed_id: UUID) -> PlacedSeed | None:
    """Get a placed seed by ID."""
    result = await db.execute(select(PlacedSeedModel).where(PlacedSeedModel.id == seed_id))
    seed = result.scalar_one_or_none()
    if seed is None:
        return None
    return _to_schema(seed)


async def list_seeds_by_world(db: AsyncSession, world_id: UUID) -> list[PlacedSeed]:
    """List all placed seeds in a world."""
    result = await db.execute(
        select(PlacedSeedModel)
        .where(PlacedSeedModel.world_id == world_id)
        .order_by(PlacedSeedModel.placed_at.asc())
    )
    seeds = result.scalars().all()
    return [_to_schema(s) for s in seeds]


async def delete_seed(db: AsyncSession, seed_id: UUID) -> bool:
    """Delete a placed seed. Returns True if deleted, False if not found."""
    result = await db.execute(delete(PlacedSeedModel).where(PlacedSeedModel.id == seed_id))
    await db.commit()
    return result.rowcount > 0


async def delete_all_seeds_in_world(db: AsyncSession, world_id: UUID) -> int:
    """Delete all placed seeds in a world. Returns count of deleted seeds."""
    result = await db.execute(delete(PlacedSeedModel).where(PlacedSeedModel.world_id == world_id))
    await db.commit()
    return result.rowcount


def _to_schema(seed: PlacedSeedModel) -> PlacedSeed:
    """Convert SQLAlchemy model to Pydantic schema."""
    return PlacedSeed(
        id=seed.id,
        world_id=seed.world_id,
        seed_type_id=seed.seed_type_id,
        position=Position(x=seed.position_x, y=seed.position_y),
        placed_at=_ensure_utc(seed.placed_at),
        metadata=seed.seed_metadata,
    )
