import uuid
from collections.abc import Sequence
from typing import Annotated

from pydantic import AwareDatetime
from pydantic import BaseModel
from pydantic import Field
from pydantic import HttpUrl
from pydantic import model_validator

from spotifagent.domain.entities.base import BaseEntity


class BaseSpotifyAccount(BaseEntity):
    token_type: str = Field(..., max_length=512)
    token_access: str = Field(..., max_length=512)
    token_refresh: str = Field(..., max_length=512)
    token_expires_at: AwareDatetime


class SpotifyAccount(BaseSpotifyAccount):
    id: int
    user_id: uuid.UUID


class SpotifyAccountCreate(BaseSpotifyAccount):
    pass


class SpotifyAccountUpdate(BaseEntity):
    token_type: str | None = Field(None, max_length=512)
    token_access: str | None = Field(None, max_length=512)
    token_refresh: str | None = Field(None, max_length=512)
    token_expires_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def validate_one_field_set(self):
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided for update")
        return self


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
