import uuid
from dataclasses import dataclass
from typing import Self

from museflow.domain.entities.track import Track
from museflow.domain.types import GenreTag
from museflow.domain.types import MoodTag
from museflow.domain.utils.text import normalize_text


@dataclass(frozen=True, kw_only=True)
class TrackNormalized:
    name: str
    artists: list[str]

    @classmethod
    def create(cls, name: str, artists: list[str]) -> Self:
        return cls(
            name=normalize_text(name),
            artists=[normalize_text(artist) for artist in artists],
        )


@dataclass(frozen=True, kw_only=True)
class TrackKnowIdentifiers:
    """Value Object representing the tracks a user already knows."""

    fingerprints: frozenset[str]

    def is_known(self, track: Track) -> bool:
        return track.fingerprint in self.fingerprints


@dataclass(frozen=True, kw_only=True)
class TrackEnrichment:
    track_id: uuid.UUID
    genres: list[GenreTag]
    moods: list[MoodTag]
