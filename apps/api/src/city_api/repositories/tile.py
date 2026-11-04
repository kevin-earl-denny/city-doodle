"""Tile repository - data access for tiles."""

import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import and_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from city_api.models import Tile as TileModel
from city_api.schemas import TerrainData, Tile, TileCreate, TileUpdate

logger = logging.getLogger(__name__)


def _ensure_utc(dt: datetime) -> datetime:
    """Ensure datetime is timezone-aware (UTC). SQLite returns naive datetimes."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


async def create_tile(db: AsyncSession, tile_create: TileCreate) -> Tile:
    """Create a new tile."""
    tile = TileModel(
        world_id=tile_create.world_id,
        tx=tile_create.tx,
        ty=tile_create.ty,
        terrain_data={},
        features={},
    )
    db.add(tile)
    await db.commit()
    await db.refresh(tile)
    return _to_schema(tile)


async def get_tile(db: AsyncSession, tile_id: UUID) -> TileModel | None:
    """Get a tile by ID (returns SQLAlchemy model)."""
    result = await db.execute(select(TileModel).where(TileModel.id == tile_id))
    return result.scalar_one_or_none()


async def get_tile_schema(db: AsyncSession, tile_id: UUID) -> Tile | None:
    """Get a tile by ID as Pydantic schema."""
    tile = await get_tile(db, tile_id)
    if tile is None:
        return None
    return _to_schema(tile)


async def get_tile_by_coords(db: AsyncSession, world_id: UUID, tx: int, ty: int) -> Tile | None:
    """Get a tile by world and coordinates."""
    result = await db.execute(
        select(TileModel).where(
            TileModel.world_id == world_id,
            TileModel.tx == tx,
            TileModel.ty == ty,
        )
    )
    tile = result.scalar_one_or_none()
    if tile is None:
        return None
    return _to_schema(tile)


async def list_tiles_by_world(
    db: AsyncSession,
    world_id: UUID,
    min_tx: int | None = None,
    max_tx: int | None = None,
    min_ty: int | None = None,
    max_ty: int | None = None,
) -> list[Tile]:
    """List tiles in a world, optionally filtered by bounding box."""
    conditions = [TileModel.world_id == world_id]

    if min_tx is not None:
        conditions.append(TileModel.tx >= min_tx)
    if max_tx is not None:
        conditions.append(TileModel.tx <= max_tx)
    if min_ty is not None:
        conditions.append(TileModel.ty >= min_ty)
    if max_ty is not None:
        conditions.append(TileModel.ty <= max_ty)

    result = await db.execute(select(TileModel).where(and_(*conditions)))
    tiles = result.scalars().all()
    return [_to_schema(t) for t in tiles]


async def update_tile(db: AsyncSession, tile_id: UUID, tile_update: TileUpdate) -> Tile | None:
    """Update a tile. Returns None if tile not found."""
    result = await db.execute(select(TileModel).where(TileModel.id == tile_id))
    tile = result.scalar_one_or_none()
    if tile is None:
        return None

    if tile_update.terrain_data is not None:
        tile.terrain_data = tile_update.terrain_data.model_dump()
    if tile_update.features is not None:
        tile.features = tile_update.features
    tile.version += 1

    await db.commit()
    await db.refresh(tile)
    return _to_schema(tile)


async def get_or_create_tile(
    db: AsyncSession, world_id: UUID, tx: int, ty: int
) -> tuple[Tile, bool]:
    """Get a tile by coordinates, creating it if it doesn't exist.

    Uses an atomic INSERT ... ON CONFLICT DO NOTHING to avoid race conditions
    when concurrent requests try to create the same tile simultaneously.

    Returns a tuple of (tile, created) where created is True if a new tile was made.
    """
    stmt = (
        pg_insert(TileModel)
        .values(world_id=world_id, tx=tx, ty=ty, terrain_data={}, features={})
        .on_conflict_do_nothing(index_elements=["world_id", "tx", "ty"])
        .returning(TileModel)
    )
    result = await db.execute(stmt)
    tile = result.scalar_one_or_none()

    if tile is not None:
        # INSERT succeeded — new row was created
        await db.commit()
        return _to_schema(tile), True

    # Row already existed (conflict), fetch it
    await db.rollback()
    existing = await get_tile_by_coords(db, world_id, tx, ty)

    if existing is not None:
        return existing, False

    # The conflicting row was deleted between our INSERT and SELECT.
    # Retry the INSERT once — it should succeed now that the row is gone.
    logger.warning(
        "Tile (%s, %d, %d) vanished between conflict and SELECT; retrying INSERT",
        world_id,
        tx,
        ty,
    )
    retry_result = await db.execute(stmt)
    retried_tile = retry_result.scalar_one_or_none()

    if retried_tile is not None:
        await db.commit()
        return _to_schema(retried_tile), True

    # Another conflict on the retry — fetch one more time
    await db.rollback()
    existing = await get_tile_by_coords(db, world_id, tx, ty)
    if existing is not None:
        return existing, False

    raise RuntimeError(
        f"Failed to get or create tile ({world_id}, {tx}, {ty}) "
        "after retry — persistent race condition"
    )


def _to_schema(tile: TileModel) -> Tile:
    """Convert SQLAlchemy model to Pydantic schema."""
    return Tile(
        id=tile.id,
        world_id=tile.world_id,
        tx=tile.tx,
        ty=tile.ty,
        terrain_data=TerrainData.model_validate(tile.terrain_data)
        if tile.terrain_data
        else TerrainData(),
        features=tile.features if tile.features else {},
        terrain_status=tile.terrain_status or "pending",
        terrain_error=tile.terrain_error,
        created_at=_ensure_utc(tile.created_at),
        updated_at=_ensure_utc(tile.updated_at),
    )


async def update_terrain_status(
    db: AsyncSession,
    tile_id: UUID,
    status: str,
    error: str | None = None,
) -> None:
    """Update terrain_status (and optionally terrain_error) for a tile."""
    values: dict = {"terrain_status": status}
    if error is not None:
        values["terrain_error"] = error
    elif status != "failed":
        # Clear any previous error when status is not failed
        values["terrain_error"] = None
    await db.execute(update(TileModel).where(TileModel.id == tile_id).values(**values))
    await db.commit()
    logger.info("Updated terrain_status for tile %s to %s", tile_id, status)
