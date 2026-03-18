import uuid
from abc import ABC
from dataclasses import dataclass
from dataclasses import field

from museflow.domain.types import AlbumType
from museflow.domain.types import ArtistSource
from museflow.domain.types import MusicProvider
from museflow.domain.types import TrackSource
from museflow.domain.utils.text import generate_fingerprint
from museflow.domain.utils.text import unidecode_lower_text


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
    top_position: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "genres", [unidecode_lower_text(g) for g in self.genres])


@dataclass(frozen=True, kw_only=True)
class Artist(BaseMediaItem):
    sources: ArtistSource = ArtistSource(0)

    @property
    def is_top(self) -> bool:
        return ArtistSource.TOP in self.sources


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
    album_type: AlbumType | None = None


@dataclass(frozen=True, kw_only=True)
class Track(BaseMediaItem):
    artists: list[TrackArtist] = field(default_factory=list)
    album: Album | None = None

    sources: TrackSource = TrackSource(0)

    isrc: str | None = None
    fingerprint: str = ""

    duration_ms: int

    def __str__(self) -> str:
        return f"{', '.join([artist.name for artist in self.artists])} - {self.name}".replace("'", "\\'")

    def __post_init__(self):
        super().__post_init__()

        if not self.fingerprint:
            fingerprint_val = generate_fingerprint(
                name=self.name,
                artist_names=[artist.name for artist in self.artists],
            )
            object.__setattr__(self, "fingerprint", fingerprint_val)

    @property
    def is_top(self) -> bool:
        return TrackSource.TOP in self.sources

    @property
    def is_saved(self) -> bool:
        return TrackSource.SAVED in self.sources

    @property
    def is_playlist(self) -> bool:
        return TrackSource.PLAYLIST in self.sources


@dataclass(frozen=True, kw_only=True)
class TrackSuggested:
    name: str
    artists: list[str] = field(default_factory=list)
    advisor_id: str | None = None
    score: float | None = None
    duration_ms: int | None = None

    def __str__(self) -> str:
        return f"{', '.join(self.artists)} - {self.name}".replace("'", "\\'")


@dataclass(frozen=True, kw_only=True)
class Playlist(BaseProviderEntity):
    snapshot_id: str | None = None

    tracks: list[Track] = field(default_factory=list)
