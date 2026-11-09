import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Self

from museflow.domain.entities.track import Track
from museflow.domain.enums import GenreTag
from museflow.domain.enums import MoodTag
from museflow.domain.types import LocaleCode
from museflow.domain.utils.text import normalize_numbers
from museflow.domain.utils.text import normalize_text
from museflow.domain.utils.text import strip_title_extras


@dataclass(frozen=True, kw_only=True)
class TrackNormalized:
    """A track's name and artists, normalized for a fuzzy comparison (not for the fingerprint)."""

    name: str
    name_base: str  # the main part of the name, without e.g. "(Interlude)" or " - Bonus Track"
    artists: list[str]

    @classmethod
    def create(cls, name: str, artists: list[str]) -> Self:
        return cls(
            name=normalize_numbers(normalize_text(name)),
            name_base=normalize_numbers(normalize_text(strip_title_extras(name))),
            artists=[normalize_text(artist) for artist in artists],
        )


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
