import uuid
from abc import ABC
from dataclasses import dataclass
from dataclasses import field
from datetime import datetime

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
class Track(BaseProviderEntity):
    artists: list[str] = field(default_factory=list)
    album_name: str | None = None

    fingerprint: str = ""

    played_at: datetime | None = None

    @property
    def primary_artist(self) -> str:
        return self.artists[0]

    def __str__(self) -> str:
        return f"{', '.join(self.artists)} - {self.name}".replace("'", "\\'")

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("Track.name must not be empty")
        if not self.provider_id:
            raise ValueError("Track.provider_id must not be empty")
        if not self.artists:
            raise ValueError("Track must have at least one artist")

        if not self.fingerprint:
            fingerprint_val = generate_fingerprint(
                name=self.name,
                artist_names=[self.primary_artist],
            )
            object.__setattr__(self, "fingerprint", fingerprint_val)


@dataclass(frozen=True, kw_only=True)
class TrackSuggested:
    name: str
    artists: list[str] = field(default_factory=list)
    advisor_id: str | None = None
    score: float

    @property
    def primary_artist(self) -> str:
        return self.artists[0]

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("TrackSuggested.name must not be empty")
        if not self.artists:
            raise ValueError("TrackSuggested must have at least one artist")

    def __str__(self) -> str:
        return f"{', '.join(self.artists)} - {self.name}".replace("'", "\\'")


@dataclass(frozen=True, kw_only=True)
class Playlist(BaseProviderEntity):
    snapshot_id: str | None = None

    tracks: list[Track] = field(default_factory=list)
