from museflow.application.ports.repositories.playlist import PlaylistRepository
from museflow.domain.entities.playlist import Playlist
from museflow.domain.entities.user import User


async def playlist_list(
    user: User,
    playlist_repository: PlaylistRepository,
) -> list[Playlist]:
    return await playlist_repository.list(user.id)
