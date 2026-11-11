from dataclasses import dataclass
from typing import Protocol


class RankableStats(Protocol):
    """The totals a ranking is computed from, whatever the group (artist, tag).

    Read-only properties, so that frozen dataclasses meet it.
    """

    @property
    def name(self) -> str: ...

    @property
    def track_count(self) -> int: ...

    @property
    def plays_count(self) -> int: ...

    @property
    def rated_count(self) -> int: ...

    @property
    def rated_sum(self) -> int: ...


@dataclass(frozen=True, kw_only=True)
class ArtistStats:
    artist: str
    track_count: int
    plays_count: int
    rated_count: int  # tracks whose score is in the requested range
    rated_sum: int  # sum of the scores counted in rated_count

    @property
    def name(self) -> str:
        return self.artist


@dataclass(frozen=True, kw_only=True)
class TagStats:
    tag: str  # a genre, a mood or a locale
    track_count: int
    plays_count: int
    rated_count: int  # tracks whose score is in the requested range
    rated_sum: int  # sum of the scores counted in rated_count

    @property
    def name(self) -> str:
        return self.tag


@dataclass(frozen=True, kw_only=True)
class LibraryStats:
    track_count: int
    rated_count: int  # tracks whose score is in the requested range
    rated_sum: int  # sum of the scores counted in rated_count
    unenriched_count: int  # tracks without any tag of the requested field

    @property
    def rate_avg(self) -> float:
        return self.rated_sum / self.rated_count if self.rated_count else 0.0


@dataclass(frozen=True, kw_only=True)
class Ranking[S: RankableStats]:
    stats: S
    quality_score: float | None  # None when no track of the group is rated
    overall_score: float
    rate_avg: float | None  # None when no track of the group is rated


@dataclass(frozen=True, kw_only=True)
class ArtistCandidate:
    artist: str
    avg_score: float
    rated_count: int
    total_count: int
