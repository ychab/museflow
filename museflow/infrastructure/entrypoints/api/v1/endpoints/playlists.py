from fastapi import APIRouter
from fastapi import Depends
from fastapi import Query

from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.application.use_cases.playlist_list import get_playlists
from museflow.domain.entities.user import User
from museflow.domain.enums import MusicProvider
from museflow.domain.enums import PlaylistType
from museflow.infrastructure.entrypoints.api.dependencies import get_current_user
from museflow.infrastructure.entrypoints.api.dependencies import get_page_params
from museflow.infrastructure.entrypoints.api.dependencies import get_unit_of_work
from museflow.infrastructure.entrypoints.api.schemas.common import PageParams
from museflow.infrastructure.entrypoints.api.schemas.common import PageResponse
from museflow.infrastructure.entrypoints.api.schemas.playlists import PlaylistResponse

router = APIRouter()


@router.get("", name="playlist_list")
async def list_playlists(
    type: PlaylistType | None = Query(None, description="Only the playlists of this type"),
    provider: MusicProvider | None = Query(None, description="Only the playlists of this provider"),
    page_params: PageParams = Depends(get_page_params),
    current_user: User = Depends(get_current_user),
    uow: UnitOfWorkPort = Depends(get_unit_of_work),
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
