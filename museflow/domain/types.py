from enum import StrEnum

type ScoreAdvisor = float
type ScoreReconciler = float


class MusicProvider(StrEnum):
    SPOTIFY = "spotify"


class MusicAdvisorAgent(StrEnum):
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
    PLAYED_AT = "played_at"
    RANDOM = "random"

    @property
    def nullable(self) -> bool:
        """True for nullable columns — NULLs are sorted last in both ASC and DESC."""
        return self == TrackOrderBy.PLAYED_AT


class SortOrder(StrEnum):
    ASC = "asc"
    DESC = "desc"


type TrackOrdering = list[tuple[TrackOrderBy, SortOrder]]


class AlbumType(StrEnum):
    ALBUM = "album"
    SINGLE = "single"
    COMPILATION = "compilation"
    EP = "ep"
    UNKNOWN = "unknown"
