import uuid
from abc import ABC
from abc import abstractmethod

from museflow.domain.entities.discovery import DiscoveryPlaylist


class DiscoveryPlaylistRepository(ABC):
    """Port for persisting and querying discovery playlists."""

    @abstractmethod
    async def save(self, playlist: DiscoveryPlaylist) -> DiscoveryPlaylist: ...

    @abstractmethod
    async def list(self, user_id: uuid.UUID) -> list[DiscoveryPlaylist]:
        """Return playlists for the user ordered by creation date descending. tracks=[] in all results."""
        ...

    @abstractmethod
    async def get(self, user_id: uuid.UUID, playlist_id: uuid.UUID) -> DiscoveryPlaylist | None:
        """Return a single playlist with its tracks, or None if not found."""
        ...

    @abstractmethod
    async def rate_track(self, user_id: uuid.UUID, track_id: uuid.UUID, score: int) -> None:
        """Persist a score on a track that belongs to a playlist owned by user_id.

        Raises:
            DiscoveryPlaylistNotFoundError: If the track or playlist is not found for this user.
        """
        ...
