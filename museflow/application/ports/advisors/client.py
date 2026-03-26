from abc import ABC
from abc import abstractmethod

from museflow.domain.entities.music import TrackSuggested


class AdvisorClientPort(ABC):
    """Abstract port for a music advisor client.

    This port defines the contract for clients that interact with music advisor
    services to get music recommendations.
    """

    @property
    @abstractmethod
    def display_name(self) -> str:
        """The display name of the advisor."""
        ...

    @abstractmethod
    async def get_similar_tracks(self, artist_name: str, track_name: str, limit: int = 5) -> list[TrackSuggested]:
        """Gets a list of similar tracks from the advisor.

        Args:
            artist_name: The name of the artist.
            track_name: The name of the track.
            limit: The maximum number of similar tracks to return.

        Returns:
            A list of suggested tracks.
        """
        ...

    @abstractmethod
    async def close(self) -> None:
        """Closes the client's resources, like the underlying HTTP client."""
        ...
