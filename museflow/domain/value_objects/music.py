from dataclasses import dataclass
from typing import Self

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
