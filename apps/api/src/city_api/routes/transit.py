"""Transit CRUD endpoints - stations, lines, and segments."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from city_api.database import get_db
from city_api.dependencies import get_current_user
from city_api.repositories import district as district_repo
from city_api.repositories import transit as transit_repo
from city_api.repositories import world as world_repo
from city_api.schemas import (
    DistrictUpdate,
    TransitLine,
    TransitLineBulkCreate,
    TransitLineCreate,
    TransitLineSegment,
    TransitLineSegmentBulkCreate,
    TransitLineSegmentCreate,
    TransitLineSegmentUpdate,
    TransitLineUpdate,
    TransitLineWithSegments,
    TransitNetwork,
    TransitNetworkStats,
    TransitStation,
    TransitStationBulkCreate,
    TransitStationCreate,
    TransitStationUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["transit"])


async def _verify_world_ownership(db: AsyncSession, world_id: UUID, user_id: UUID) -> None:
    """Verify that the user owns the world. Raises HTTPException if not."""
    world = await world_repo.get_world(db, world_id)
    if world is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"World {world_id} not found",
        )
    if world.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this world",
        )


async def _verify_district_exists(db: AsyncSession, district_id: UUID) -> None:
    """Verify that a district exists. Raises HTTPException if not."""
    district = await district_repo.get_district(db, district_id)
    if district is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"District {district_id} not found",
        )


# ============================================================================
# Transit Network Aggregate Endpoints
# ============================================================================


@router.get("/worlds/{world_id}/transit", response_model=TransitNetwork)
async def get_transit_network(
    world_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
) -> TransitNetwork:
    """Get the complete transit network for a world."""
    await _verify_world_ownership(db, world_id, user_id)
    return await transit_repo.get_transit_network(db, world_id)


@router.get("/worlds/{world_id}/transit/stats", response_model=TransitNetworkStats)
async def get_transit_stats(
    world_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
) -> TransitNetworkStats:
    """Get statistics about the transit network."""
    await _verify_world_ownership(db, world_id, user_id)
    return await transit_repo.get_network_stats(db, world_id)


@router.delete("/worlds/{world_id}/transit", status_code=status.HTTP_204_NO_CONTENT)
async def clear_transit_network(
    world_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
) -> None:
    """Delete all transit stations and lines in a world."""
    await _verify_world_ownership(db, world_id, user_id)
    await transit_repo.clear_transit_network(db, world_id)


# ============================================================================
# Transit Station Endpoints
# ============================================================================


@router.get("/worlds/{world_id}/transit/stations", response_model=list[TransitStation])
async def list_stations(
    world_id: UUID,
    station_type: str | None = None,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
) -> list[TransitStation]:
    """List all transit stations in a world."""
    await _verify_world_ownership(db, world_id, user_id)
    return await transit_repo.list_stations_by_world(db, world_id, station_type=station_type)


@router.post(
    "/worlds/{world_id}/transit/stations",
    response_model=TransitStation,
    status_code=status.HTTP_201_CREATED,
)
async def create_station(
    world_id: UUID,
    station_create: TransitStationCreate,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
) -> TransitStation:
    """Create a new transit station."""
    await _verify_world_ownership(db, world_id, user_id)
    await _verify_district_exists(db, station_create.district_id)
    # Override world_id from path
    station_create.world_id = world_id
    station = await transit_repo.create_station(db, station_create)
    # Mark the district as having transit access
    await district_repo.update_district(
        db, station_create.district_id, DistrictUpdate(transit_access=True)
    )
    return station


@router.post(
    "/worlds/{world_id}/transit/stations/bulk",
    response_model=list[TransitStation],
    status_code=status.HTTP_201_CREATED,
)
async def create_stations_bulk(
    world_id: UUID,
    bulk_create: TransitStationBulkCreate,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
) -> list[TransitStation]:
    """Create multiple transit stations in a single request."""
    await _verify_world_ownership(db, world_id, user_id)
    # Verify all districts exist
    for station in bulk_create.stations:
        await _verify_district_exists(db, station.district_id)
    # Override world_id from path
    for station in bulk_create.stations:
        station.world_id = world_id
    stations = await transit_repo.create_stations_bulk(db, bulk_create.stations)
    # Mark districts as having transit access
    district_ids = {s.district_id for s in bulk_create.stations}
    for did in district_ids:
        await district_repo.update_district(db, did, DistrictUpdate(transit_access=True))
    return stations


@router.get("/transit/stations/{station_id}", response_model=TransitStation)
async def get_station(
    station_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
) -> TransitStation:
    """Get a transit station by ID."""
    station = await transit_repo.get_station(db, station_id)
    if station is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transit station {station_id} not found",
        )
    await _verify_world_ownership(db, station.world_id, user_id)
    return station


@router.patch("/transit/stations/{station_id}", response_model=TransitStation)
async def update_station(
    station_id: UUID,
    station_update: TransitStationUpdate,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
) -> TransitStation:
    """Update a transit station."""
    station = await transit_repo.get_station(db, station_id)
    if station is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transit station {station_id} not found",
        )
    await _verify_world_ownership(db, station.world_id, user_id)
    if station_update.district_id is not None:
        await _verify_district_exists(db, station_update.district_id)

    updated = await transit_repo.update_station(db, station_id, station_update)
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transit station {station_id} not found",
        )
    return updated


@router.delete("/transit/stations/{station_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_station(
    station_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
) -> None:
    """Delete a transit station. Connected segments will also be deleted."""
    station = await transit_repo.get_station(db, station_id)
    if station is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transit station {station_id} not found",
        )
    await _verify_world_ownership(db, station.world_id, user_id)
    await transit_repo.delete_station(db, station_id)


# ============================================================================
# Transit Line Endpoints
# ============================================================================


@router.get("/worlds/{world_id}/transit/lines", response_model=list[TransitLine])
async def list_lines(
    world_id: UUID,
    line_type: str | None = None,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
) -> list[TransitLine]:
    """List all transit lines in a world."""
    await _verify_world_ownership(db, world_id, user_id)
    return await transit_repo.list_lines_by_world(db, world_id, line_type=line_type)


@router.post(
    "/worlds/{world_id}/transit/lines",
    response_model=TransitLine,
    status_code=status.HTTP_201_CREATED,
)
async def create_line(
    world_id: UUID,
    line_create: TransitLineCreate,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
) -> TransitLine:
    """Create a new transit line."""
    await _verify_world_ownership(db, world_id, user_id)
    # Override world_id from path
    line_create.world_id = world_id
    # CITY-536: Check for duplicate line name within this world
    existing_lines = await transit_repo.list_lines_by_world(db, world_id)
    if any(line.name == line_create.name for line in existing_lines):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f'A transit line named "{line_create.name}" already exists in this world',
        )
    return await transit_repo.create_line(db, line_create)


@router.post(
    "/worlds/{world_id}/transit/lines/bulk",
    response_model=list[TransitLine],
    status_code=status.HTTP_201_CREATED,
)
async def create_lines_bulk(
    world_id: UUID,
    bulk_create: TransitLineBulkCreate,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
) -> list[TransitLine]:
    """Create multiple transit lines in a single request."""
    await _verify_world_ownership(db, world_id, user_id)
    # Override world_id from path
    for line in bulk_create.lines:
        line.world_id = world_id
    return await transit_repo.create_lines_bulk(db, bulk_create.lines)


@router.get("/transit/lines/{line_id}", response_model=TransitLineWithSegments)
async def get_line(
    line_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
) -> TransitLineWithSegments:
    """Get a transit line by ID with all its segments."""
    line = await transit_repo.get_line_with_segments(db, line_id)
    if line is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transit line {line_id} not found",
        )
    await _verify_world_ownership(db, line.world_id, user_id)
    return line


@router.patch("/transit/lines/{line_id}", response_model=TransitLine)
async def update_line(
    line_id: UUID,
    line_update: TransitLineUpdate,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
) -> TransitLine:
    """Update a transit line."""
    line = await transit_repo.get_line(db, line_id)
    if line is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transit line {line_id} not found",
        )
    await _verify_world_ownership(db, line.world_id, user_id)

    # CITY-536: Check for duplicate line name within this world on rename
    if line_update.name is not None and line_update.name != line.name:
        existing_lines = await transit_repo.list_lines_by_world(db, line.world_id)
        if any(other.name == line_update.name for other in existing_lines if other.id != line_id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f'A transit line named "{line_update.name}" already exists in this world',
            )

    updated = await transit_repo.update_line(db, line_id, line_update)
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transit line {line_id} not found",
        )
    return updated


@router.delete("/transit/lines/{line_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_line(
    line_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
) -> None:
    """Delete a transit line. Segments are also deleted."""
    line = await transit_repo.get_line(db, line_id)
    if line is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transit line {line_id} not found",
        )
    await _verify_world_ownership(db, line.world_id, user_id)
    await transit_repo.delete_line(db, line_id)


# ============================================================================
# Transit Line Segment Endpoints
# ============================================================================


@router.get("/transit/lines/{line_id}/segments", response_model=list[TransitLineSegment])
async def list_segments(
    line_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
) -> list[TransitLineSegment]:
    """List all segments of a transit line."""
    line = await transit_repo.get_line(db, line_id)
    if line is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transit line {line_id} not found",
        )
    await _verify_world_ownership(db, line.world_id, user_id)
    return await transit_repo.list_segments_by_line(db, line_id)


@router.post(
    "/transit/lines/{line_id}/segments",
    response_model=TransitLineSegment,
    status_code=status.HTTP_201_CREATED,
)
async def create_segment(
    line_id: UUID,
    segment_create: TransitLineSegmentCreate,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
) -> TransitLineSegment:
    """Create a new line segment."""
    line = await transit_repo.get_line(db, line_id)
    if line is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transit line {line_id} not found",
        )
    await _verify_world_ownership(db, line.world_id, user_id)
    # Override line_id from path
    segment_create.line_id = line_id

    segment = await transit_repo.create_segment(db, segment_create)
    if segment is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="One or both stations do not exist",
        )
    return segment


@router.post(
    "/transit/lines/{line_id}/segments/bulk",
    response_model=list[TransitLineSegment],
    status_code=status.HTTP_201_CREATED,
)
async def create_segments_bulk(
    line_id: UUID,
    bulk_create: TransitLineSegmentBulkCreate,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
) -> list[TransitLineSegment]:
    """Create multiple line segments in a single request."""
    line = await transit_repo.get_line(db, line_id)
    if line is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transit line {line_id} not found",
        )
    await _verify_world_ownership(db, line.world_id, user_id)
    # Override line_id from path
    for segment in bulk_create.segments:
        segment.line_id = line_id
    return await transit_repo.create_segments_bulk(db, bulk_create.segments)


@router.get("/transit/segments/{segment_id}", response_model=TransitLineSegment)
async def get_segment(
    segment_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
) -> TransitLineSegment:
    """Get a line segment by ID."""
    segment = await transit_repo.get_segment(db, segment_id)
    if segment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transit segment {segment_id} not found",
        )
    # Get line to check world ownership
    line = await transit_repo.get_line(db, segment.line_id)
    if line is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transit line {segment.line_id} not found",
        )
    await _verify_world_ownership(db, line.world_id, user_id)
    return segment


@router.patch("/transit/segments/{segment_id}", response_model=TransitLineSegment)
async def update_segment(
    segment_id: UUID,
    segment_update: TransitLineSegmentUpdate,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
) -> TransitLineSegment:
    """Update a line segment."""
    segment = await transit_repo.get_segment(db, segment_id)
    if segment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transit segment {segment_id} not found",
        )
    # Get line to check world ownership
    line = await transit_repo.get_line(db, segment.line_id)
    if line is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transit line {segment.line_id} not found",
        )
    await _verify_world_ownership(db, line.world_id, user_id)

    updated = await transit_repo.update_segment(db, segment_id, segment_update)
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Update failed - segment not found or invalid station reference",
        )
    return updated


@router.delete("/transit/segments/{segment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_segment(
    segment_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
) -> None:
    """Delete a line segment."""
    segment = await transit_repo.get_segment(db, segment_id)
    if segment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transit segment {segment_id} not found",
        )
    # Get line to check world ownership
    line = await transit_repo.get_line(db, segment.line_id)
    if line is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transit line {segment.line_id} not found",
        )
    await _verify_world_ownership(db, line.world_id, user_id)
    await transit_repo.delete_segment(db, segment_id)
