from abc import ABC
from abc import abstractmethod

from museflow.domain.entities.taste import TasteProfile
from museflow.domain.entities.track import Track
from museflow.domain.entities.track import TrackSuggested
from museflow.domain.enums import DiscoveryFocus
from museflow.domain.enums import GenreTag
from museflow.domain.enums import MoodTag
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
        focus: DiscoveryFocus,
        advisor_limit: int,
        genre: GenreTag | None = None,
        mood: MoodTag | None = None,
        custom_instructions: str | None = None,
        excluded_tracks: list[TrackSuggested] | None = None,
        blacklisted_artists: list[str] | None = None,
        blacklisted_tracks: list[str] | None = None,
        liked_tracks: list[Track] | None = None,
    ) -> DiscoveryTasteStrategy: ...

    @abstractmethod
    async def close(self) -> None:
        """Closes the advisor's resources, like the underlying HTTP client."""
        ...
