import uuid
from abc import ABC
from abc import abstractmethod

from museflow.domain.entities.playlist import Playlist


class PlaylistRepository(ABC):
    """Port for persisting and querying playlists."""

    @abstractmethod
    async def save(self, playlist: Playlist) -> Playlist: ...

    @abstractmethod
    async def list(self, user_id: uuid.UUID) -> list[Playlist]:
        """Return playlists for the user ordered by creation date descending. tracks=[] in all results."""
        ...

    @abstractmethod
    async def get(self, user_id: uuid.UUID, playlist_id: uuid.UUID) -> Playlist | None:
        """Return a single playlist with its tracks, or None if not found."""
        ...
