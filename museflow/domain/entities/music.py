import uuid
from abc import ABC
from dataclasses import dataclass
from dataclasses import field

from museflow.domain.types import MusicProvider


@dataclass(frozen=True, kw_only=True)
class BaseProviderEntity(ABC):
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    user_id: uuid.UUID

    name: str
    slug: str

    provider: MusicProvider = MusicProvider.SPOTIFY
    provider_id: str


@dataclass(frozen=True, kw_only=True)
class BaseMediaItem(BaseProviderEntity):
    popularity: int | None = None

    is_saved: bool = False
    is_top: bool = False
    top_position: int | None = None


@dataclass(frozen=True, kw_only=True)
class Artist(BaseMediaItem):
    genres: list[str] = field(default_factory=list)


@dataclass(frozen=True, kw_only=True)
class TrackArtist:
    """Represents an artist associated with a specific track.

    This is a simplified representation used within a track context, primarily
    for display and linking purposes.
    """

    provider_id: str
    name: str


@dataclass(frozen=True, kw_only=True)
class Track(BaseMediaItem):
    artists: list[TrackArtist] = field(default_factory=list)


@dataclass(frozen=True, kw_only=True)
class Playlist(BaseProviderEntity):
    tracks: list[Track]
