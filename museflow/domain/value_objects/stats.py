from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class ArtistStats:
    artist: str
    quality_score: float | None  # None for artists with no rated tracks
    overall_score: float
    rate_avg: float | None  # None for artists with no rated tracks
    rated_count: int
    track_count: int
    plays_count: int


@dataclass(frozen=True, kw_only=True)
class ArtistCandidate:
    artist: str
    avg_score: float
    rated_count: int
    total_count: int
