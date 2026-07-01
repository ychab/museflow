from dataclasses import dataclass
from dataclasses import field
from datetime import datetime

from museflow.domain.entities.base import BaseEntity
from museflow.domain.enums import GenreTag
from museflow.domain.enums import MoodTag
from museflow.domain.enums import MusicProvider
from museflow.domain.enums import TrackSource
from museflow.domain.types import LocaleCode
from museflow.domain.utils.text import generate_fingerprint


@dataclass(frozen=True, kw_only=True)
class ProviderLink:
    provider: MusicProvider
    provider_id: str


@dataclass(frozen=True, kw_only=True)
class Track(BaseEntity):
    artists: list[str] = field(default_factory=list)
    album_name: str | None = None

    fingerprint: str = ""

    provider_links: list[ProviderLink] = field(default_factory=list)

    played_at_first: datetime | None = None
    played_at_last: datetime | None = None
    played_count: int = 1

    source: TrackSource = TrackSource.HISTORY
    score: int | None = None
    score_skipped: bool = False

    genres: list[GenreTag] = field(default_factory=list)
    moods: list[MoodTag] = field(default_factory=list)
    locale: LocaleCode | None = None

    @property
    def primary_artist(self) -> str:
        return self.artists[0]

    def get_provider_id(self, provider: MusicProvider) -> str | None:
        return next((link.provider_id for link in self.provider_links if link.provider == provider), None)

    def __str__(self) -> str:
        return f"{', '.join(self.artists)} - {self.name}".replace("'", "\\'")

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("Track.name must not be empty")
        if not self.provider_links:
            raise ValueError("Track must have at least one provider link")
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
