import enum

from museflow.domain.types import TrackSource


class SourceFilter(enum.StrEnum):
    ALL = "all"
    HISTORY = "history"
    DISCOVERY = "discovery"

    def to_track_source(self) -> TrackSource | None:
        if self == SourceFilter.HISTORY:
            return TrackSource.HISTORY
        if self == SourceFilter.DISCOVERY:
            return TrackSource.DISCOVERY
        return None


class ArtistSortBy(enum.StrEnum):
    TRACK_COUNT = "track_count"  # Raw breadth: distinct tracks by the artist
    PLAYS_COUNT = "plays_count"  # Raw depth: total plays across the artist's tracks
    RATE_AVG = "rate_avg"  # Raw quality: simple average of the artist's track ratings
    QUALITY = "quality"  # Smoothed quality: confidence-weighted average, small samples pulled toward the mean
    OVERALL = "overall"  # Blended ranking: breadth x depth x smoothed quality (default sort)


class TrackSortBy(enum.StrEnum):
    SCORE = "score"
    PLAYED_COUNT = "played_count"
