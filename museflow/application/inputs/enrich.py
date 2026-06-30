from dataclasses import dataclass

from pydantic import BaseModel
from pydantic import field_validator

from museflow.domain.types import GenreTag
from museflow.domain.types import MoodTag


@dataclass(frozen=True, kw_only=True)
class EnrichTracksConfigInput:
    force: bool = False
    batch_size: int = 200
    limit: int | None = None


class EnrichEntryInput(BaseModel):
    fingerprint: str
    genres: list[GenreTag] = []
    moods: list[MoodTag] = []

    @field_validator("genres", mode="before")
    @classmethod
    def _filter_genres(cls, v: object) -> list[str]:
        if not isinstance(v, list):
            return []
        return [g for g in v if isinstance(g, str) and g in GenreTag._value2member_map_]

    @field_validator("moods", mode="before")
    @classmethod
    def _filter_moods(cls, v: object) -> list[str]:
        if not isinstance(v, list):
            return []
        return [m for m in v if isinstance(m, str) and m in MoodTag._value2member_map_]
