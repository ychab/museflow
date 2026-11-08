from abc import ABC
from abc import abstractmethod

from museflow.domain.value_objects.track import TrackPlay


class TrackPlayRepository(ABC):
    """Port for the listens of the tracks: the only source of their play data."""

    @abstractmethod
    async def bulk_create(self, plays: list[TrackPlay]) -> int:
        """Saves the plays, skipping those already saved (same track and time), and returns how many were new."""
