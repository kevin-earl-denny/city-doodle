"""Transit repository - data access for stations, lines, and segments."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from city_api.models.transit import TransitLine as TransitLineModel
from city_api.models.transit import TransitLineSegment as TransitLineSegmentModel
from city_api.models.transit import TransitStation as TransitStationModel
from city_api.schemas import (
    TransitLine,
    TransitLineCreate,
    TransitLineSegment,
    TransitLineSegmentCreate,
    TransitLineSegmentUpdate,
    TransitLineUpdate,
    TransitLineWithSegments,
    TransitNetwork,
    TransitNetworkStats,
    TransitStation,
    TransitStationCreate,
    TransitStationUpdate,
)
from city_api.schemas.transit import Point


def _ensure_utc(dt: datetime) -> datetime:
    """Ensure datetime is timezone-aware (UTC)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


# ============================================================================
# Transit Station Operations
# ============================================================================


async def create_station(db: AsyncSession, station_create: TransitStationCreate) -> TransitStation:
    """Create a new transit station."""
    station = TransitStationModel(
        world_id=station_create.world_id,
        district_id=station_create.district_id,
        station_type=station_create.station_type.value,  # Pass string value for PostgreSQL enum
        name=station_create.name,
        position_x=station_create.position_x,
        position_y=station_create.position_y,
        is_terminus=station_create.is_terminus,
    )
    db.add(station)
    await db.commit()
    await db.refresh(station)
    return _station_to_schema(station)


async def create_stations_bulk(
    db: AsyncSession, stations: list[TransitStationCreate]
) -> list[TransitStation]:
    """Create multiple stations at once."""
    models = [
        TransitStationModel(
            world_id=s.world_id,
            district_id=s.district_id,
            station_type=s.station_type.value,  # Pass string value for PostgreSQL enum
            name=s.name,
            position_x=s.position_x,
            position_y=s.position_y,
            is_terminus=s.is_terminus,
        )
        for s in stations
    ]
    db.add_all(models)
    await db.commit()
    for m in models:
        await db.refresh(m)
    return [_station_to_schema(m) for m in models]


async def get_station(db: AsyncSession, station_id: UUID) -> TransitStation | None:
    """Get a transit station by ID."""
    result = await db.execute(
        select(TransitStationModel).where(TransitStationModel.id == station_id)
    )
    station = result.scalar_one_or_none()
    if station is None:
        return None
    return _station_to_schema(station)


async def get_station_model(db: AsyncSession, station_id: UUID) -> TransitStationModel | None:
    """Get a station model by ID (for internal use)."""
    result = await db.execute(
        select(TransitStationModel).where(TransitStationModel.id == station_id)
    )
    return result.scalar_one_or_none()


async def list_stations_by_world(
    db: AsyncSession, world_id: UUID, station_type: str | None = None
) -> list[TransitStation]:
    """List all transit stations in a world."""
    query = select(TransitStationModel).where(TransitStationModel.world_id == world_id)
    if station_type:
        query = query.where(TransitStationModel.station_type == station_type)
    result = await db.execute(query)
    stations = result.scalars().all()
    return [_station_to_schema(s) for s in stations]


async def update_station(
    db: AsyncSession, station_id: UUID, station_update: TransitStationUpdate
) -> TransitStation | None:
    """Update a transit station."""
    result = await db.execute(
        select(TransitStationModel).where(TransitStationModel.id == station_id)
    )
    station = result.scalar_one_or_none()
    if station is None:
        return None

    if station_update.district_id is not None:
        station.district_id = station_update.district_id
    if station_update.station_type is not None:
        station.station_type = (
            station_update.station_type.value
        )  # Pass string value for PostgreSQL enum
    if station_update.name is not None:
        station.name = station_update.name
    if station_update.position_x is not None:
        station.position_x = station_update.position_x
    if station_update.position_y is not None:
        station.position_y = station_update.position_y
    if station_update.is_terminus is not None:
        station.is_terminus = station_update.is_terminus

    await db.commit()
    await db.refresh(station)
    return _station_to_schema(station)


async def delete_station(db: AsyncSession, station_id: UUID) -> bool:
    """Delete a transit station. Connected segments are deleted via CASCADE.

    After deletion, any transit lines left with zero segments are also removed
    to prevent orphaned line records (CITY-301).
    """
    # Find lines that reference this station (via segments) before deletion
    seg_query = select(TransitLineSegmentModel.line_id).where(
        (TransitLineSegmentModel.from_station_id == station_id)
        | (TransitLineSegmentModel.to_station_id == station_id)
    )
    seg_result = await db.execute(seg_query)
    affected_line_ids = list({row[0] for row in seg_result.all()})

    # Delete the station (CASCADE removes its segments)
    result = await db.execute(
        delete(TransitStationModel).where(TransitStationModel.id == station_id)
    )
    if result.rowcount == 0:
        await db.commit()
        return False

    # Clean up orphaned lines
    await _delete_orphaned_lines(db, affected_line_ids)
    await db.commit()
    return True


# ============================================================================
# Transit Line Operations
# ============================================================================


async def create_line(db: AsyncSession, line_create: TransitLineCreate) -> TransitLine:
    """Create a new transit line."""
    line = TransitLineModel(
        world_id=line_create.world_id,
        line_type=line_create.line_type.value,  # Pass string value for PostgreSQL enum
        name=line_create.name,
        color=line_create.color,
        is_auto_generated=line_create.is_auto_generated,
    )
    db.add(line)
    await db.commit()
    await db.refresh(line)
    return _line_to_schema(line)


async def create_lines_bulk(db: AsyncSession, lines: list[TransitLineCreate]) -> list[TransitLine]:
    """Create multiple lines at once."""
    models = [
        TransitLineModel(
            world_id=line.world_id,
            line_type=line.line_type.value,  # Pass string value for PostgreSQL enum
            name=line.name,
            color=line.color,
            is_auto_generated=line.is_auto_generated,
        )
        for line in lines
    ]
    db.add_all(models)
    await db.commit()
    for m in models:
        await db.refresh(m)
    return [_line_to_schema(m) for m in models]


async def get_line(db: AsyncSession, line_id: UUID) -> TransitLine | None:
    """Get a transit line by ID."""
    result = await db.execute(select(TransitLineModel).where(TransitLineModel.id == line_id))
    line = result.scalar_one_or_none()
    if line is None:
        return None
    return _line_to_schema(line)


async def get_line_model(db: AsyncSession, line_id: UUID) -> TransitLineModel | None:
    """Get a line model by ID (for internal use)."""
    result = await db.execute(select(TransitLineModel).where(TransitLineModel.id == line_id))
    return result.scalar_one_or_none()


async def get_line_with_segments(db: AsyncSession, line_id: UUID) -> TransitLineWithSegments | None:
    """Get a transit line with all its segments."""
    result = await db.execute(
        select(TransitLineModel)
        .where(TransitLineModel.id == line_id)
        .options(selectinload(TransitLineModel.segments))
    )
    line = result.scalar_one_or_none()
    if line is None:
        return None
    return _line_with_segments_to_schema(line)


async def list_lines_by_world(
    db: AsyncSession, world_id: UUID, line_type: str | None = None
) -> list[TransitLine]:
    """List all transit lines in a world."""
    query = select(TransitLineModel).where(TransitLineModel.world_id == world_id)
    if line_type:
        query = query.where(TransitLineModel.line_type == line_type)
    result = await db.execute(query)
    lines = result.scalars().all()
    return [_line_to_schema(line) for line in lines]


async def list_lines_with_segments_by_world(
    db: AsyncSession, world_id: UUID
) -> list[TransitLineWithSegments]:
    """List all transit lines with segments in a world."""
    result = await db.execute(
        select(TransitLineModel)
        .where(TransitLineModel.world_id == world_id)
        .options(selectinload(TransitLineModel.segments))
    )
    lines = result.scalars().all()
    return [_line_with_segments_to_schema(line) for line in lines]


async def update_line(
    db: AsyncSession, line_id: UUID, line_update: TransitLineUpdate
) -> TransitLine | None:
    """Update a transit line."""
    result = await db.execute(select(TransitLineModel).where(TransitLineModel.id == line_id))
    line = result.scalar_one_or_none()
    if line is None:
        return None

    if line_update.line_type is not None:
        line.line_type = line_update.line_type.value  # Pass string value for PostgreSQL enum
    if line_update.name is not None:
        line.name = line_update.name
    if line_update.color is not None:
        line.color = line_update.color
    if line_update.is_auto_generated is not None:
        line.is_auto_generated = line_update.is_auto_generated

    await db.commit()
    await db.refresh(line)
    return _line_to_schema(line)


async def delete_line(db: AsyncSession, line_id: UUID) -> bool:
    """Delete a transit line. Segments are deleted via CASCADE."""
    result = await db.execute(delete(TransitLineModel).where(TransitLineModel.id == line_id))
    await db.commit()
    return result.rowcount > 0


# ============================================================================
# Transit Line Segment Operations
# ============================================================================


async def create_segment(
    db: AsyncSession, segment_create: TransitLineSegmentCreate
) -> TransitLineSegment | None:
    """Create a new line segment. Returns None if line or stations don't exist."""
    # Verify line exists
    line = await get_line_model(db, segment_create.line_id)
    if line is None:
        return None

    # Verify stations exist
    from_station = await get_station_model(db, segment_create.from_station_id)
    to_station = await get_station_model(db, segment_create.to_station_id)
    if from_station is None or to_station is None:
        return None

    geometry = [p.model_dump() for p in segment_create.geometry] if segment_create.geometry else []

    segment = TransitLineSegmentModel(
        line_id=segment_create.line_id,
        from_station_id=segment_create.from_station_id,
        to_station_id=segment_create.to_station_id,
        geometry=geometry,
        is_underground=segment_create.is_underground,
        order_in_line=segment_create.order_in_line,
    )
    db.add(segment)
    await db.commit()
    await db.refresh(segment)
    return _segment_to_schema(segment)


async def create_segments_bulk(
    db: AsyncSession, segments: list[TransitLineSegmentCreate]
) -> list[TransitLineSegment]:
    """Create multiple segments at once. Skips segments with invalid references."""
    created = []
    for segment_create in segments:
        segment = await create_segment(db, segment_create)
        if segment is not None:
            created.append(segment)
    return created


async def get_segment(db: AsyncSession, segment_id: UUID) -> TransitLineSegment | None:
    """Get a line segment by ID."""
    result = await db.execute(
        select(TransitLineSegmentModel).where(TransitLineSegmentModel.id == segment_id)
    )
    segment = result.scalar_one_or_none()
    if segment is None:
        return None
    return _segment_to_schema(segment)


async def list_segments_by_line(db: AsyncSession, line_id: UUID) -> list[TransitLineSegment]:
    """List all segments of a line, ordered by order_in_line."""
    result = await db.execute(
        select(TransitLineSegmentModel)
        .where(TransitLineSegmentModel.line_id == line_id)
        .order_by(TransitLineSegmentModel.order_in_line)
    )
    segments = result.scalars().all()
    return [_segment_to_schema(s) for s in segments]


async def update_segment(
    db: AsyncSession, segment_id: UUID, segment_update: TransitLineSegmentUpdate
) -> TransitLineSegment | None:
    """Update a line segment."""
    result = await db.execute(
        select(TransitLineSegmentModel).where(TransitLineSegmentModel.id == segment_id)
    )
    segment = result.scalar_one_or_none()
    if segment is None:
        return None

    if segment_update.from_station_id is not None:
        # Verify station exists
        station = await get_station_model(db, segment_update.from_station_id)
        if station is None:
            return None
        segment.from_station_id = segment_update.from_station_id
    if segment_update.to_station_id is not None:
        # Verify station exists
        station = await get_station_model(db, segment_update.to_station_id)
        if station is None:
            return None
        segment.to_station_id = segment_update.to_station_id
    if segment_update.geometry is not None:
        segment.geometry = [p.model_dump() for p in segment_update.geometry]
    if segment_update.is_underground is not None:
        segment.is_underground = segment_update.is_underground
    if segment_update.order_in_line is not None:
        segment.order_in_line = segment_update.order_in_line

    await db.commit()
    await db.refresh(segment)
    return _segment_to_schema(segment)


async def delete_segment(db: AsyncSession, segment_id: UUID) -> bool:
    """Delete a line segment.

    After deletion, if the parent line has zero remaining segments it is also
    removed to prevent orphaned line records (CITY-301).
    """
    # Look up the parent line before deleting the segment
    seg_result = await db.execute(
        select(TransitLineSegmentModel.line_id).where(TransitLineSegmentModel.id == segment_id)
    )
    row = seg_result.one_or_none()
    parent_line_id = row[0] if row else None

    result = await db.execute(
        delete(TransitLineSegmentModel).where(TransitLineSegmentModel.id == segment_id)
    )
    if result.rowcount == 0:
        await db.commit()
        return False

    # Clean up orphaned parent line
    if parent_line_id:
        await _delete_orphaned_lines(db, [parent_line_id])
    await db.commit()
    return True


# ============================================================================
# Orphan Cleanup Helpers (CITY-301)
# ============================================================================


async def _delete_orphaned_lines(db: AsyncSession, line_ids: list[UUID]) -> int:
    """Delete any of the given lines that have zero remaining segments.

    Returns the number of lines deleted.
    """
    if not line_ids:
        return 0

    deleted = 0
    for line_id in line_ids:
        count_result = await db.execute(
            select(TransitLineSegmentModel.id).where(TransitLineSegmentModel.line_id == line_id)
        )
        if len(count_result.all()) == 0:
            await db.execute(delete(TransitLineModel).where(TransitLineModel.id == line_id))
            deleted += 1
    return deleted


# ============================================================================
# Network Operations
# ============================================================================


async def get_transit_network(db: AsyncSession, world_id: UUID) -> TransitNetwork:
    """Get the complete transit network for a world."""
    stations = await list_stations_by_world(db, world_id)
    lines = await list_lines_with_segments_by_world(db, world_id)
    return TransitNetwork(world_id=world_id, stations=stations, lines=lines)


async def get_network_stats(db: AsyncSession, world_id: UUID) -> TransitNetworkStats:
    """Get statistics about a transit network."""
    stations = await list_stations_by_world(db, world_id)
    lines = await list_lines_by_world(db, world_id)

    # Count by type
    stations_by_type: dict[str, int] = {}
    for station in stations:
        type_name = station.station_type.value
        stations_by_type[type_name] = stations_by_type.get(type_name, 0) + 1

    lines_by_type: dict[str, int] = {}
    total_segments = 0
    for line in lines:
        type_name = line.line_type.value
        lines_by_type[type_name] = lines_by_type.get(type_name, 0) + 1
        # Get segment count for this line
        segments = await list_segments_by_line(db, line.id)
        total_segments += len(segments)

    return TransitNetworkStats(
        world_id=world_id,
        total_stations=len(stations),
        total_lines=len(lines),
        total_segments=total_segments,
        stations_by_type=stations_by_type,
        lines_by_type=lines_by_type,
    )


async def clear_transit_network(db: AsyncSession, world_id: UUID) -> tuple[int, int]:
    """Delete all stations and lines in a world. Returns (lines_deleted, stations_deleted).

    Lines and segments are deleted via CASCADE when lines are deleted.
    Stations are deleted after lines.
    """
    # Delete lines first (segments will be deleted via CASCADE)
    lines_result = await db.execute(
        delete(TransitLineModel).where(TransitLineModel.world_id == world_id)
    )
    # Then delete stations
    stations_result = await db.execute(
        delete(TransitStationModel).where(TransitStationModel.world_id == world_id)
    )
    await db.commit()
    return (lines_result.rowcount, stations_result.rowcount)


# ============================================================================
# Schema Converters
# ============================================================================


def _station_to_schema(station: TransitStationModel) -> TransitStation:
    """Convert SQLAlchemy model to Pydantic schema."""
    return TransitStation(
        id=station.id,
        world_id=station.world_id,
        district_id=station.district_id,
        station_type=station.station_type,
        name=station.name,
        position_x=station.position_x,
        position_y=station.position_y,
        is_terminus=station.is_terminus,
        created_at=_ensure_utc(station.created_at),
        updated_at=_ensure_utc(station.updated_at),
    )


def _line_to_schema(line: TransitLineModel) -> TransitLine:
    """Convert SQLAlchemy model to Pydantic schema."""
    return TransitLine(
        id=line.id,
        world_id=line.world_id,
        line_type=line.line_type,
        name=line.name,
        color=line.color,
        is_auto_generated=line.is_auto_generated,
        created_at=_ensure_utc(line.created_at),
        updated_at=_ensure_utc(line.updated_at),
    )


def _line_with_segments_to_schema(line: TransitLineModel) -> TransitLineWithSegments:
    """Convert SQLAlchemy model to Pydantic schema with segments."""
    return TransitLineWithSegments(
        id=line.id,
        world_id=line.world_id,
        line_type=line.line_type,
        name=line.name,
        color=line.color,
        is_auto_generated=line.is_auto_generated,
        segments=[_segment_to_schema(s) for s in line.segments] if line.segments else [],
        created_at=_ensure_utc(line.created_at),
        updated_at=_ensure_utc(line.updated_at),
    )


def _segment_to_schema(segment: TransitLineSegmentModel) -> TransitLineSegment:
    """Convert SQLAlchemy model to Pydantic schema."""
    return TransitLineSegment(
        id=segment.id,
        line_id=segment.line_id,
        from_station_id=segment.from_station_id,
        to_station_id=segment.to_station_id,
        geometry=[Point(**p) for p in segment.geometry] if segment.geometry else [],
        is_underground=segment.is_underground,
        order_in_line=segment.order_in_line,
        created_at=_ensure_utc(segment.created_at),
        updated_at=_ensure_utc(segment.updated_at),
    )
