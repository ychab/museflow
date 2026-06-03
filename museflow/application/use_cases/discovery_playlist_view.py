import uuid

from museflow.application.ports.repositories.discovery import DiscoveryPlaylistRepository
from museflow.domain.entities.discovery import DiscoveryPlaylist
from museflow.domain.entities.user import User
from museflow.domain.exceptions import DiscoveryPlaylistNotFoundError


async def discovery_playlist_view(
    user: User,
    playlist_id: uuid.UUID,
    discovery_playlist_repository: DiscoveryPlaylistRepository,
) -> DiscoveryPlaylist:
    playlist = await discovery_playlist_repository.get(user.id, playlist_id)
    if playlist is None:
        raise DiscoveryPlaylistNotFoundError()
    return playlist
