import uuid
from abc import ABC
from dataclasses import dataclass
from dataclasses import field

from museflow.domain.types import MusicProvider
from museflow.domain.utils.text import generate_fingerprint


@dataclass(frozen=True, kw_only=True)
class BaseProviderEntity(ABC):
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    user_id: uuid.UUID

    name: str

    provider: MusicProvider = MusicProvider.SPOTIFY
    provider_id: str


@dataclass(frozen=True, kw_only=True)
class BaseMediaItem(BaseProviderEntity):
    popularity: int | None = None
    genres: list[str] = field(default_factory=list)

    is_saved: bool = False
    is_top: bool = False
    top_position: int | None = None


@dataclass(frozen=True, kw_only=True)
class Artist(BaseMediaItem):
    pass


@dataclass(frozen=True, kw_only=True)
class TrackArtist:
    """Represents an artist associated with a specific track.

    This is a simplified representation used within a track context, primarily
    for display and linking purposes.
    """

    provider_id: str
    name: str


@dataclass(frozen=True, kw_only=True)
class Album:
    provider_id: str
    name: str
    album_type: str | None = None


@dataclass(frozen=True, kw_only=True)
class Track(BaseMediaItem):
    artists: list[TrackArtist] = field(default_factory=list)
    album: Album | None = None

    isrc: str | None = None
    fingerprint: str = ""

    duration_ms: int

    def __post_init__(self):
        if not self.fingerprint:
            fingerprint_val = generate_fingerprint(
                name=self.name,
                artist_names=[artist.name for artist in self.artists],
            )
            object.__setattr__(self, "fingerprint", fingerprint_val)


@dataclass(frozen=True, kw_only=True)
class TrackSuggested:
    name: str
    artists: list[str]
    advisor_id: str | None = None
    score: float | None = None


@dataclass(frozen=True, kw_only=True)
class Playlist(BaseProviderEntity):
    snapshot_id: str | None = None

    tracks: list[Track]
