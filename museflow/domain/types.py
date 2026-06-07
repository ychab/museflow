from enum import IntFlag
from enum import StrEnum

type TrackOrdering = list[tuple[TrackOrderBy, SortOrder]]
type ScoreAdvisor = float
type ScoreReconciler = float

DISCOVERY_TRACK_SCORE_MIN: int = 0
DISCOVERY_TRACK_SCORE_MAX: int = 10


class TrackSource(IntFlag):
    HISTORY = 1
    DISCOVERY = 2


class MusicProvider(StrEnum):
    SPOTIFY = "spotify"


class MusicAdvisor(StrEnum):
    GEMINI = "gemini"


class TasteProfiler(StrEnum):
    GEMINI = "gemini"


class DiscoveryFocus(StrEnum):
    EXPANSION = "expansion"
    ROOTS_REVIVAL = "roots_revival"
    CULTURAL_BRIDGE = "cultural_bridge"


class TrackOrderBy(StrEnum):
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"
    PLAYED_AT_LAST = "played_at_last"
    PLAYED_AT_FIRST = "played_at_first"
    PLAYED_COUNT = "played_count"
    RANDOM = "random"

    @property
    def nullable(self) -> bool:
        """True for nullable columns — NULLs are sorted last in both ASC and DESC."""
        return self in (TrackOrderBy.PLAYED_AT_LAST, TrackOrderBy.PLAYED_AT_FIRST)


class SortOrder(StrEnum):
    ASC = "asc"
    DESC = "desc"
