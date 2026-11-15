from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.domain.entities.playlist import Playlist
from museflow.domain.entities.user import User
from museflow.domain.enums import PlaylistType


async def get_playlists(
    user: User,
    uow: UnitOfWorkPort,
    type: PlaylistType | None = None,
) -> list[Playlist]:
    async with uow:
        return await uow.playlists.get_list(user.id, type=type)
