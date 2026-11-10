from abc import ABC
from abc import abstractmethod

from museflow.domain.entities.playlist import Playlist
from museflow.domain.entities.track import Track
from museflow.domain.enums import PlaylistType


class ProviderLibraryPort(ABC):
    """A port defining the contract for interacting with a music provider's library.

    This interface abstracts track search and playlist creation on a specific music provider.
    """

    @abstractmethod
    async def search_tracks(
        self,
        track: str,
        artists: list[str] | None = None,
        is_new: bool = False,
        is_underground: bool = False,
        page_size: int = 20,
        max_pages: int | None = None,
        log_enabled: bool = True,
    ) -> list[Track]:
        """Retrieves a list of tracks based on the search criteria.

        A provider may follow a strict query that finds nothing with a looser one: the caller checks the candidates.

        Args:
            track: The name of the track to search for.
            artists: The track's artists, primary first. A provider may filter on the primary one only.
            is_new: Whether to include only new tracks (periodicity depends on the provider).
            is_underground: Whether to include underground tracks (depends on the provider).
            page_size: An optional maximum number of tracks per page.
            max_pages: The maximum number of pages to retrieve.
            log_enabled: Whether to write logs.

        Returns:
            A list of `Track` entities.

        Raises:
            ProviderSearchQueryInvalidError: If the provider rejects the query as malformed.
        """
        ...

    @abstractmethod
    async def search_artist_tracks(
        self,
        artist: str,
        page_size: int = 10,
        max_pages: int | None = None,
        log_enabled: bool = True,
    ) -> list[Track]:
        """Retrieves tracks of an artist, in the provider's relevance order.

        The provider may also return tracks of artists with a close name: the caller checks the candidates.

        Raises:
            ProviderSearchQueryInvalidError: If the provider rejects the query as malformed.
        """
        ...

    @abstractmethod
    async def create_playlist(
        self,
        name: str,
        type: PlaylistType,
        tracks: list[Track],
        is_public: bool = False,
    ) -> Playlist:
        """Create a user's playlist with the given tracks.

        Args:
            name: The name of the playlist
            type: The type of playlist being created (e.g. discovery)
            tracks: A list of tracks to add to the playlist
            is_public: Whether the playlist should be public or private

        Returns:
            The entity's playlist created.
        """
        ...

    @abstractmethod
    async def delete_playlist(self, provider_playlist_id: str) -> None:
        """Remove a playlist from the user's provider library."""
        ...

    @abstractmethod
    async def play_track(self, track_provider_id: str) -> None:
        """Start playing a track immediately on the user's active provider device.

        Raises:
            ProviderNoActiveDeviceError: If no device is currently active.
            ProviderPremiumRequiredError: If the user's account doesn't support playback control.
        """
        ...
