import uuid
from abc import ABC
from dataclasses import dataclass
from dataclasses import field

from museflow.domain.types import MusicProvider


@dataclass(frozen=True, kw_only=True)
class BaseMusicItem(ABC):
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    user_id: uuid.UUID

    name: str
    slug: str
    popularity: int | None = None

    is_saved: bool = False
    is_top: bool = False
    top_position: int | None = None

    provider: MusicProvider = MusicProvider.SPOTIFY
    provider_id: str


@dataclass(frozen=True, kw_only=True)
class Artist(BaseMusicItem):
    genres: list[str] = field(default_factory=list)


@dataclass(frozen=True, kw_only=True)
class TrackArtist:
    provider_id: str
    name: str


@dataclass(frozen=True, kw_only=True)
class Track(BaseMusicItem):
    artists: list[TrackArtist] = field(default_factory=list)
