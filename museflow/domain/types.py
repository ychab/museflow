from enum import IntFlag
from enum import StrEnum
from typing import Self

type ScoreAdvisor = float
type ScoreReconciler = float


class MusicProvider(StrEnum):
    SPOTIFY = "spotify"


class MusicAdvisorSimilar(StrEnum):
    LASTFM = "last.fm"
    GEMINI = "gemini"


class TasteProfiler(StrEnum):
    GEMINI = "gemini"


class ArtistSource(IntFlag):
    """Bitmask: an artist can belong to multiple sources simultaneously."""

    TOP = 1


class TrackSource(IntFlag):
    """Bitmask: a track can belong to multiple sources simultaneously."""

    TOP = 1
    SAVED = 2
    PLAYLIST = 4
    HISTORY = 8
    SEARCH = 16

    @classmethod
    def from_flags(
        cls,
        top: bool | None = None,
        saved: bool | None = None,
        playlist: bool | None = None,
        history: bool | None = None,
    ) -> Self | None:
        mask = cls(0)

        if top:
            mask |= cls.TOP
        if saved:
            mask |= cls.SAVED
        if playlist:
            mask |= cls.PLAYLIST
        if history:
            mask |= cls.HISTORY

        return mask if mask != 0 else None


class TrackOrderBy(StrEnum):
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"
    POPULARITY = "popularity"
    TOP_POSITION = "top_position"
    PLAYED_AT = "played_at"
    ADDED_AT = "added_at"
    RANDOM = "random"

    @property
    def nullable(self) -> bool:
        """True for nullable columns — NULLs are sorted last in both ASC and DESC."""
        return self in (TrackOrderBy.PLAYED_AT, TrackOrderBy.ADDED_AT)


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

    @property
    def priority(self) -> int:
        return {
            AlbumType.ALBUM: 0,
            AlbumType.EP: 1,
            AlbumType.SINGLE: 2,
            AlbumType.COMPILATION: 3,
            AlbumType.UNKNOWN: 4,
        }[self]
