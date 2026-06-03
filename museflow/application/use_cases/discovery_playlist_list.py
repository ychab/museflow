from museflow.application.ports.repositories.discovery import DiscoveryPlaylistRepository
from museflow.domain.entities.discovery import DiscoveryPlaylist
from museflow.domain.entities.user import User


async def discovery_playlist_list(
    user: User,
    discovery_playlist_repository: DiscoveryPlaylistRepository,
) -> list[DiscoveryPlaylist]:
    return await discovery_playlist_repository.list(user.id)
