import uuid
from abc import ABC
from abc import abstractmethod

from museflow.domain.value_objects.taste import ListeningPeriod
from museflow.domain.value_objects.track import TrackPlay


class TrackPlayRepository(ABC):
    """Port for the listens of the tracks: the only source of their play data."""

    @abstractmethod
    async def bulk_create(self, plays: list[TrackPlay]) -> int:
        """Saves the plays, skipping those already saved (same track and time), and returns how many were new."""

    @abstractmethod
    async def count_played_tracks(self, user_id: uuid.UUID, min_score: int | None = None) -> int:
        """Counts the user's tracks played at least once, rated `min_score` or more when given."""

    @abstractmethod
    async def get_periods(
        self,
        user_id: uuid.UUID,
        periods: int,
        tracks_per_period: int,
        min_score: int | None = None,
    ) -> list[ListeningPeriod]:
        """Splits the user's plays, oldest first, into `periods` periods holding the same number of plays.

        Each period lists its `tracks_per_period` most played tracks, most played first; a track played in several
        periods is in each. Fewer periods come back when there are fewer plays than periods.

        Args:
            min_score: only the plays of the tracks rated this or more count, in the periods and their tracks.
        """
