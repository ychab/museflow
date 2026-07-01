from dataclasses import dataclass
from typing import Annotated

from pydantic import BaseModel
from pydantic import field_validator
from pydantic.functional_validators import BeforeValidator

from museflow.domain.enums import GenreTag
from museflow.domain.enums import MoodTag
from museflow.domain.types import LocaleCode
from museflow.domain.utils.text import validate_locale


@dataclass(frozen=True, kw_only=True)
class EnrichTracksConfigInput:
    force: bool = False
    batch_size: int = 200
    limit: int | None = None


class EnrichEntryInput(BaseModel):
    fingerprint: str

    genres: list[GenreTag] = []
    moods: list[MoodTag] = []
    locale: Annotated[LocaleCode | None, BeforeValidator(validate_locale)] = None

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
