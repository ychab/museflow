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
    TRACK_COUNT = "track_count"
    SCORE_AVG = "score_avg"
    SCORE_BAYESIAN = "score_bayesian"


class TrackSortBy(enum.StrEnum):
    SCORE = "score"
    PLAYED_COUNT = "played_count"
