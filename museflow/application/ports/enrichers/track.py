from abc import ABC
from abc import abstractmethod

from museflow.domain.entities.track import Track
from museflow.domain.value_objects.track import TrackEnrichment


class TrackEnricherPort(ABC):
    """Abstract port for a service that infers genre and mood metadata for tracks."""

    @abstractmethod
    async def enrich_tracks(self, tracks: list[Track]) -> list[TrackEnrichment]: ...

    @abstractmethod
    async def close(self) -> None:
        """Closes the enricher's resources, like the underlying HTTP client."""
        ...
