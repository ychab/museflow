from collections.abc import Sequence
from typing import Annotated

from pydantic import AwareDatetime
from pydantic import BaseModel
from pydantic import Field
from pydantic import HttpUrl


class SpotifyTrackArtist(BaseModel):
    id: str
    name: str


class SpotifyItem(BaseModel):
    id: str
    name: str
    href: HttpUrl


class SpotifyPlaylist(SpotifyItem):
    pass


class SpotifyArtist(SpotifyItem):
    popularity: int
    genres: list[str]


class SpotifyTrack(SpotifyItem):
    popularity: int
    artists: list[SpotifyTrackArtist]


class SpotifySavedTrack(BaseModel):
    added_at: AwareDatetime | None = None
    track: SpotifyTrack


class SpotifyPlaylistTrack(BaseModel):
    item: SpotifyTrack


class SpotifyPage[T: SpotifyItem | SpotifySavedTrack | SpotifyPlaylistTrack](BaseModel):
    items: Sequence[T]
    total: Annotated[int, Field(ge=0)]
    limit: Annotated[int, Field(ge=0)]
    offset: Annotated[int, Field(ge=0)]


class SpotifyPlaylistPage(SpotifyPage[SpotifyPlaylist]): ...


class SpotifySavedTrackPage(SpotifyPage[SpotifySavedTrack]): ...


class SpotifyPlaylistTrackPage(SpotifyPage[SpotifyPlaylistTrack]): ...


class SpotifyTopArtistPage(SpotifyPage[SpotifyArtist]): ...


class SpotifyTopTrackPage(SpotifyPage[SpotifyTrack]): ...
