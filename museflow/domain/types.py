from enum import IntFlag
from enum import StrEnum
from typing import Self


class MusicProvider(StrEnum):
    SPOTIFY = "spotify"


class MusicAdvisor(StrEnum):
    LASTFM = "last.fm"


class ArtistSource(IntFlag):
    """Bitmask: an artist can belong to multiple sources simultaneously."""

    TOP = 1


class TrackSource(IntFlag):
    """Bitmask: a track can belong to multiple sources simultaneously."""

    TOP = 1
    SAVED = 2
    PLAYLIST = 4

    @classmethod
    def from_flags(
        cls,
        top: bool | None = None,
        saved: bool | None = None,
        playlist: bool | None = None,
    ) -> Self | None:
        mask = cls(0)

        if top:
            mask |= cls.TOP
        if saved:
            mask |= cls.SAVED
        if playlist:
            mask |= cls.PLAYLIST

        return mask if mask != 0 else None


class TrackOrderBy(StrEnum):
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"
    POPULARITY = "popularity"
    TOP_POSITION = "top_position"
    RANDOM = "random"


class SortOrder(StrEnum):
    ASC = "asc"
    DESC = "desc"


class AlbumType(StrEnum):
    ALBUM = "album"
    SINGLE = "single"
    COMPILATION = "compilation"
    EP = "ep"
    UNKNOWN = "unknown"
