import uuid
from dataclasses import dataclass
from datetime import datetime

from museflow.domain.entities.track import Track
from museflow.domain.enums import GenreTag
from museflow.domain.enums import MoodTag
from museflow.domain.types import LocaleCode


@dataclass(frozen=True, kw_only=True)
class TrackKnownIdentifiers:
    """Value Object representing the tracks a user already knows."""

    fingerprints: frozenset[str]

    def is_known(self, track: Track) -> bool:
        return track.fingerprint in self.fingerprints


@dataclass(frozen=True, kw_only=True)
class TrackPlay:
    """One listen of a track."""

    track_id: uuid.UUID
    played_at: datetime


@dataclass(frozen=True, kw_only=True)
class TrackEnrichment:
    track_id: uuid.UUID
    genres: list[GenreTag]
    moods: list[MoodTag]
    locales: list[LocaleCode] | None = None
