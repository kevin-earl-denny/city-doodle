"""District CRUD endpoints."""

import logging
import traceback
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from city_api.database import get_db
from city_api.dependencies import get_current_user
from city_api.repositories import district as district_repo
from city_api.repositories import world as world_repo
from city_api.schemas import District, DistrictBulkCreate, DistrictCreate, DistrictUpdate

logger = logging.getLogger(__name__)

router = APIRouter(tags=["districts"])


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


# ============================================================================
# District CRUD
# ============================================================================


@router.get("/worlds/{world_id}/districts", response_model=list[District])
async def list_districts(
    world_id: UUID,
    historic_only: bool = False,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
) -> list[District]:
    """List all districts in a world."""
    logger.debug(f"Listing districts: world_id={world_id}, historic_only={historic_only}")
    try:
        await _verify_world_ownership(db, world_id, user_id)
        result = await district_repo.list_districts_by_world(
            db, world_id, historic_only=historic_only
        )
        logger.debug(f"Found {len(result)} districts")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list districts: {type(e).__name__}: {e}\n{traceback.format_exc()}")
        raise


@router.post(
    "/worlds/{world_id}/districts",
    response_model=District,
    status_code=status.HTTP_201_CREATED,
)
async def create_district(
    world_id: UUID,
    district_create: DistrictCreate,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
) -> District:
    """Create a new district."""
    logger.debug(
        f"Creating district: world_id={world_id}, type={district_create.type}, "
        f"type_value={district_create.type.value}"
    )
    try:
        await _verify_world_ownership(db, world_id, user_id)
        # Override world_id from path
        district_create.world_id = world_id
        result = await district_repo.create_district(db, district_create)
        logger.debug(f"District created: id={result.id}")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to create district: world_id={world_id}, type={district_create.type}, "
            f"error={type(e).__name__}: {e}\n{traceback.format_exc()}"
        )
        raise


@router.post(
    "/worlds/{world_id}/districts/bulk",
    response_model=list[District],
    status_code=status.HTTP_201_CREATED,
)
async def create_districts_bulk(
    world_id: UUID,
    bulk_create: DistrictBulkCreate,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
) -> list[District]:
    """Create multiple districts in a single request."""
    await _verify_world_ownership(db, world_id, user_id)
    # Override world_id from path
    for d in bulk_create.districts:
        d.world_id = world_id
    return await district_repo.create_districts_bulk(db, bulk_create.districts)


@router.get("/districts/{district_id}", response_model=District)
async def get_district(
    district_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
) -> District:
    """Get a district by ID."""
    district = await district_repo.get_district(db, district_id)
    if district is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"District {district_id} not found",
        )
    await _verify_world_ownership(db, district.world_id, user_id)
    return district


@router.patch("/districts/{district_id}", response_model=District)
async def update_district(
    district_id: UUID,
    district_update: DistrictUpdate,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
) -> District:
    """Update a district."""
    district = await district_repo.get_district(db, district_id)
    if district is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"District {district_id} not found",
        )
    await _verify_world_ownership(db, district.world_id, user_id)

    updated = await district_repo.update_district(db, district_id, district_update)
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"District {district_id} not found",
        )
    return updated


@router.delete("/districts/{district_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_district(
    district_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
) -> None:
    """Delete a district."""
    district = await district_repo.get_district(db, district_id)
    if district is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"District {district_id} not found",
        )
    await _verify_world_ownership(db, district.world_id, user_id)
    await district_repo.delete_district(db, district_id)


@router.delete("/worlds/{world_id}/districts", status_code=status.HTTP_204_NO_CONTENT)
async def delete_all_districts(
    world_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
) -> None:
    """Delete all districts in a world."""
    await _verify_world_ownership(db, world_id, user_id)
    await district_repo.clear_districts(db, world_id)
