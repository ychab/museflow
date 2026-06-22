import uuid

from museflow.application.ports.repositories.playlist import PlaylistRepository
from museflow.domain.entities.playlist import Playlist
from museflow.domain.entities.user import User
from museflow.domain.exceptions import PlaylistNotFoundError


async def playlist_view(
    user: User,
    playlist_id: uuid.UUID,
    playlist_repository: PlaylistRepository,
) -> Playlist:
    playlist = await playlist_repository.get(user.id, playlist_id)
    if playlist is None:
        raise PlaylistNotFoundError()
    return playlist
