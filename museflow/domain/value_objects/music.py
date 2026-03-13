from dataclasses import dataclass
from typing import Self

from museflow.domain.entities.music import Track
from museflow.domain.utils.text import normalize_text


@dataclass(frozen=True, kw_only=True)
class TrackNormalized:
    name: str
    artists: list[str]
    duration_ms: int | None = None

    @classmethod
    def create(cls, name: str, artists: list[str], duration_ms: int | None = None) -> Self:
        return cls(
            name=normalize_text(name),
            artists=[normalize_text(artist) for artist in artists],
            duration_ms=duration_ms,
        )


@dataclass(frozen=True, kw_only=True)
class TrackKnowIdentifiers:
    """Value Object representing the tracks a user already knows."""

    isrcs: frozenset[str]
    fingerprints: frozenset[str]

    def is_known(self, track: Track) -> bool:
        if track.isrc and track.isrc in self.isrcs:
            return True

        if track.fingerprint in self.fingerprints:
            return True

        return False
