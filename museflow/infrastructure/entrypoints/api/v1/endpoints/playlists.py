from typing import Annotated

from fastapi import APIRouter
from fastapi import Query

from museflow.application.use_cases.playlist_list import get_playlists
from museflow.domain.enums import MusicProvider
from museflow.domain.enums import PlaylistType
from museflow.infrastructure.entrypoints.api.dependencies import CurrentUserDep
from museflow.infrastructure.entrypoints.api.dependencies import PageParamsDep
from museflow.infrastructure.entrypoints.api.dependencies import UnitOfWorkDep
from museflow.infrastructure.entrypoints.api.v1.schemas.common import PageResponse
from museflow.infrastructure.entrypoints.api.v1.schemas.playlists import PlaylistResponse

router = APIRouter()


@router.get("", name="playlist_list")
async def list_playlists(
    *,
    type: Annotated[PlaylistType | None, Query(description="Only the playlists of this type")] = None,
    provider: Annotated[MusicProvider | None, Query(description="Only the playlists of this provider")] = None,
    page_params: PageParamsDep,
    current_user: CurrentUserDep,
    uow: UnitOfWorkDep,
) -> PageResponse[PlaylistResponse]:
    """The user's playlists, the newest first, without their tracks."""
    page = await get_playlists(
        user=current_user,
        uow=uow,
        type=type,
        provider=provider,
        limit=page_params.limit,
        offset=page_params.offset,
    )
    return PageResponse[PlaylistResponse].model_validate(page)
