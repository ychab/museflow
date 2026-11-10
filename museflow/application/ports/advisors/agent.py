from abc import ABC
from abc import abstractmethod

from museflow.domain.entities.taste import TasteProfile
from museflow.domain.entities.track import Track
from museflow.domain.enums import DiscoveryFocus
from museflow.domain.value_objects.llm import LLMUsage
from museflow.domain.value_objects.taste import DiscoveryArtistStrategy
from museflow.domain.value_objects.taste import TrackPicked


class AdvisorPort(ABC):
    """Abstract port for an AI advisor that picks artists, then tracks among theirs, for a discovery playlist."""

    @property
    @abstractmethod
    def display_name(self) -> str:
        """The display name of the advisor."""
        ...

    @property
    @abstractmethod
    def usages(self) -> list[LLMUsage]:
        """Tokens and cost of the calls made since the adapter was created, per step and model."""
        ...

    @abstractmethod
    async def get_discovery_artists(
        self,
        profile: TasteProfile,
        artists_limit: int,
        prompt: str | None = None,
        focus: DiscoveryFocus | None = None,
        excluded_artists: list[str] | None = None,
        blacklisted_artists: list[str] | None = None,
        blacklisted_tracks: list[str] | None = None,
        liked_tracks: list[Track] | None = None,
        disliked_tracks: list[Track] | None = None,
        covered_artists: dict[str, int] | None = None,
    ) -> DiscoveryArtistStrategy:
        """Asks for artists matching the profile, each with the sound wanted from them: their tracks come later.

        Args:
            excluded_artists: Artists already suggested in this session, not to be suggested again.
            liked_tracks: Tracks the user rated high, as taste anchors.
            disliked_tracks: Tracks the user rated low, as what to steer away from.
            covered_artists: Artists the user owns the most tracks of, with their track count: their catalogue is
                already well covered. A coverage, not a preference: plays and scores do not count.
        """
        ...

    @abstractmethod
    async def pick_discovery_tracks(
        self,
        strategy: DiscoveryArtistStrategy,
        candidates: dict[str, list[Track]],
        tracks_limit: int,
        max_tracks_per_artist: int,
        prompt: str | None = None,
        focus: DiscoveryFocus | None = None,
    ) -> list[TrackPicked]:
        """Asks to choose, among the candidates only, the tracks that fit the strategy and the request.

        Args:
            strategy: The artists step's reply, whose reasoning and per-artist sound guide the choice.
            candidates: Catalogue tracks unknown to the user, per suggested artist name.
            tracks_limit: The most tracks to pick: fewer, or none, when nothing fits.

        Returns:
            The picked candidates; a pick that is not one of them is dropped.
        """
        ...

    @abstractmethod
    async def close(self) -> None:
        """Closes the advisor's resources, like the underlying HTTP client."""
        ...
