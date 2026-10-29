import uuid

from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.domain.entities.playlist import Playlist
from museflow.domain.entities.user import User
from museflow.domain.exceptions import PlaylistNotFoundError


async def playlist_view(
    user: User,
    playlist_id: uuid.UUID,
    uow: UnitOfWorkPort,
) -> Playlist:
    async with uow:
        playlist = await uow.playlists.get(user.id, playlist_id)

    if playlist is None:
        raise PlaylistNotFoundError()

    return playlist
