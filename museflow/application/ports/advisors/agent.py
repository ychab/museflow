from abc import ABC
from abc import abstractmethod

from museflow.domain.entities.taste import TasteProfile
from museflow.domain.entities.track import Track
from museflow.domain.enums import DiscoveryFocus
from museflow.domain.value_objects.llm import LLMUsage
from museflow.domain.value_objects.taste import DiscoveryArtistStrategy
from museflow.domain.value_objects.taste import TrackPicked


class AdvisorPort(ABC):
    """Abstract port for an AI advisor that picks artists, then tracks among theirs, for a discovery playlist.

    It also picks among the unknown tracks of artists the user already knows, for an exploration playlist.
    """

    @property
    @abstractmethod
    def display_name(self) -> str:
        """The display name of the advisor."""
        ...

    @abstractmethod
    def pop_usages(self) -> list[LLMUsage]:
        """Tokens and cost of the calls made since the last pop, per step and model; the next pop starts afresh.

        A use case saves what it pops: what it popped is never handed over again, so a run never counts a call twice.
        """
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
            max_tracks_per_artist: The most picks per credited artist, a featured appearance included.

        Returns:
            The picked candidates; a pick that is not one of them is dropped.
        """
        ...

    @abstractmethod
    async def pick_exploration_tracks(
        self,
        candidates: dict[str, list[Track]],
        liked_tracks: dict[str, list[Track]],
        tracks_limit: int,
        max_tracks_per_artist: int,
        prompt: str | None = None,
    ) -> list[TrackPicked]:
        """Asks to choose, among the candidates only, the tracks the user missed from artists they already love.

        No strategy guides the choice: the artists come from the user's data, not from an artists step.

        Args:
            candidates: Catalogue tracks unknown to the user, per artist name.
            liked_tracks: The user's best-rated tracks of a candidate artist, per artist name: what they love in them.
            tracks_limit: The most tracks to pick: fewer, or none, when nothing fits.
            max_tracks_per_artist: The most picks per credited artist, a featured appearance included.
            prompt: An optional request on the sound wanted.

        Returns:
            The picked candidates; a pick that is not one of them is dropped.
        """
        ...

    @abstractmethod
    async def close(self) -> None:
        """Closes the advisor's resources, like the underlying HTTP client."""
        ...
