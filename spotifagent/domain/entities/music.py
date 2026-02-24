import uuid
from enum import StrEnum

from pydantic import BaseModel
from pydantic import Field
from pydantic import PositiveInt
from pydantic import computed_field

from slugify import slugify

from spotifagent.domain.entities.base import BaseEntity


class MusicProvider(StrEnum):
    SPOTIFY = "spotify"


class BaseUserProvider(BaseEntity):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    user_id: uuid.UUID

    provider: MusicProvider = MusicProvider.SPOTIFY
    provider_id: str = Field(..., max_length=512)


class BaseMusicItem(BaseUserProvider):
    name: str = Field(..., max_length=255)

    popularity: int | None = Field(default=None, ge=0, le=100)

    is_saved: bool = False

    is_top: bool = False
    top_position: PositiveInt | None = None

    @computed_field
    def slug(self) -> str:
        return slugify(self.name)


class Artist(BaseMusicItem):
    genres: list[str]


class TrackArtist(BaseModel):
    provider_id: str
    name: str


class Track(BaseMusicItem):
    artists: list[TrackArtist]
