from dataclasses import dataclass
from typing import Self

from museflow.domain.entities.music import Track
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
