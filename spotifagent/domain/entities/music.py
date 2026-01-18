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


class TopItem(BaseEntity):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    user_id: uuid.UUID

    name: str = Field(..., max_length=255)
    popularity: int = Field(..., ge=0, le=100)
    position: PositiveInt

    provider: MusicProvider = MusicProvider.SPOTIFY
    provider_id: str = Field(..., max_length=512)

    @computed_field
    def slug(self) -> str:
        return slugify(self.name)


class TopTrackArtist(BaseModel):
    provider_id: str
    name: str


class TopArtist(TopItem):
    genres: list[str]


class TopTrack(TopItem):
    artists: list[TopTrackArtist]
