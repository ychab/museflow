from museflow.application.outputs.pagination import Page
from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.domain.entities.playlist import Playlist
from museflow.domain.entities.user import User
from museflow.domain.enums import MusicProvider
from museflow.domain.enums import PlaylistType


async def get_playlists(
    user: User,
    uow: UnitOfWorkPort,
    type: PlaylistType | None = None,
    provider: MusicProvider | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> Page[Playlist]:
    async with uow:
        playlists = await uow.playlists.get_list(user.id, type=type, provider=provider, limit=limit, offset=offset)
        total = await uow.playlists.count(user.id, type=type, provider=provider)

    return Page(items=playlists, total=total, limit=limit, offset=offset)
