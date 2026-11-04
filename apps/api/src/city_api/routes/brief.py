"""World Brief endpoint: natural-language terrain description → structured brief."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from city_api.brief.compiler import compile_brief
from city_api.brief.schema import BriefRequest, BriefResponse
from city_api.brief.service import BriefError, generate_brief
from city_api.dependencies import get_current_user

router = APIRouter(prefix="/worlds", tags=["worlds"])


@router.post("/brief", response_model=BriefResponse)
async def create_world_brief(
    request: BriefRequest,
    user_id: UUID = Depends(get_current_user),
) -> BriefResponse:
    """Survey a described place.

    Returns a World Brief plus the WorldSettings it compiles to. The world is
    not created here; the client shows the brief for review, then calls
    POST /worlds with the returned settings.
    """
    try:
        raw = await generate_brief(request, user_id)
    except BriefError as e:
        raise HTTPException(status_code=e.status, detail=e.public_message) from e

    brief, settings, warnings = compile_brief(raw)
    return BriefResponse(brief=brief, settings=settings, warnings=warnings)
