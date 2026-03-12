from enum import StrEnum


class MusicProvider(StrEnum):
    SPOTIFY = "spotify"


class MusicAdvisor(StrEnum):
    LASTFM = "last.fm"


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
