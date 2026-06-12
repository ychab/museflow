from abc import ABC
from abc import abstractmethod

from museflow.domain.entities.music import Playlist
from museflow.domain.entities.music import Track


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

        Args:
            track: The name of the track to search for.
            artists: A list of artist names to filter by.
            is_new: Whether to include only new tracks (periodicity depends on the provider).
            is_underground: Whether to include underground tracks (depends on the provider).
            page_size: An optional maximum number of tracks per page.
            max_pages: The maximum number of pages to retrieve.
            log_enabled: Whether to write logs.

        Returns:
            A list of `Track` entities.
        """
        ...

    @abstractmethod
    async def create_playlist(self, name: str, tracks: list[Track], is_public: bool = False) -> Playlist:
        """Create a user's playlist with the given tracks.

        Args:
            name: The name of the playlist
            tracks: A list of tracks to add to the playlist
            is_public: Whether the playlist should be public or private

        Returns:
            The entity's playlist created.
        """
        ...

    @abstractmethod
    async def play_track(self, track_provider_id: str) -> None:
        """Start playing a track immediately on the user's active provider device.

        Raises:
            ProviderNoActiveDeviceException: If no device is currently active.
            ProviderPremiumRequiredException: If the user's account doesn't support playback control.
        """
        ...
