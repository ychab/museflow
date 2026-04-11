from abc import ABC
from abc import abstractmethod

from museflow.domain.entities.music import TrackSuggested
from museflow.domain.entities.taste import TasteProfile
from museflow.domain.types import DiscoveryFocus
from museflow.domain.value_objects.taste import DiscoveryTasteStrategy


class AdvisorAgentPort(ABC):
    """Abstract port for an AI advisor agent that generates discovery strategies."""

    @property
    @abstractmethod
    def display_name(self) -> str:
        """The display name of the advisor agent."""
        ...

    @abstractmethod
    async def get_discovery_strategy(
        self,
        profile: TasteProfile,
        focus: DiscoveryFocus,
        similar_limit: int,
        genre: str | None = None,
        mood: str | None = None,
        custom_instructions: str | None = None,
        excluded_tracks: list[TrackSuggested] | None = None,
    ) -> DiscoveryTasteStrategy: ...

    @abstractmethod
    async def close(self) -> None:
        """Closes the agent's resources, like the underlying HTTP client."""
        ...
