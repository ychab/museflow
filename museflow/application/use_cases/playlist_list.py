from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.domain.entities.playlist import Playlist
from museflow.domain.entities.user import User


async def get_playlists(
    user: User,
    uow: UnitOfWorkPort,
) -> list[Playlist]:
    async with uow:
        return await uow.playlists.get_list(user.id)
