from abc import ABC
from abc import abstractmethod

from museflow.domain.entities.track import Track
from museflow.domain.enums import EnrichField
from museflow.domain.value_objects.llm import LLMUsage
from museflow.domain.value_objects.track import TrackEnrichment


class TrackEnricherPort(ABC):
    """Abstract port for a service that infers genre and mood metadata for tracks."""

    @abstractmethod
    def take_usages(self) -> list[LLMUsage]:
        """Tokens and cost of the calls made since the last take, per step and model; the next take starts afresh.

        A use case saves each take: what it took is never handed over again, so a run never counts a call twice.
        """
        ...

    @abstractmethod
    async def enrich_tracks(self, tracks: list[Track], fields: frozenset[EnrichField]) -> list[TrackEnrichment]: ...

    @abstractmethod
    async def close(self) -> None:
        """Closes the enricher's resources, like the underlying HTTP client."""
        ...
