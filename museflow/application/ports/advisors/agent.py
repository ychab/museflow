from abc import ABC
from abc import abstractmethod

from museflow.domain.entities.taste import TasteProfile
from museflow.domain.entities.track import Track
from museflow.domain.entities.track import TrackSuggested
from museflow.domain.enums import DiscoveryFocus
from museflow.domain.value_objects.llm import LLMUsage
from museflow.domain.value_objects.taste import DiscoveryTasteStrategy


class AdvisorPort(ABC):
    """Abstract port for an AI advisor that generates discovery strategies."""

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
    async def get_discovery_strategy(
        self,
        profile: TasteProfile,
        advisor_limit: int,
        prompt: str | None = None,
        focus: DiscoveryFocus | None = None,
        excluded_tracks: list[TrackSuggested] | None = None,
        known_tracks: list[TrackSuggested] | None = None,
        blacklisted_artists: list[str] | None = None,
        blacklisted_tracks: list[str] | None = None,
        liked_tracks: list[Track] | None = None,
        disliked_tracks: list[Track] | None = None,
        covered_artists: dict[str, int] | None = None,
    ) -> DiscoveryTasteStrategy:
        """Asks for new tracks matching the profile.

        Args:
            excluded_tracks: Earlier suggestions of the session, not to be suggested again.
            known_tracks: Earlier suggestions of the session the user already knew: the next picks should dig deeper.
            liked_tracks: Tracks the user rated high, as taste anchors.
            disliked_tracks: Tracks the user rated low, as what to steer away from.
            covered_artists: Artists the user owns the most tracks of, with their track count: their catalogue is
                already well covered. A coverage, not a preference: plays and scores do not count.
        """
        ...

    @abstractmethod
    async def close(self) -> None:
        """Closes the advisor's resources, like the underlying HTTP client."""
        ...
