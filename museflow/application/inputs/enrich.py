from dataclasses import dataclass

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import field_serializer
from pydantic import field_validator

from museflow.domain.enums import EnrichField
from museflow.domain.enums import GenreTag
from museflow.domain.enums import MoodTag
from museflow.domain.types import LocaleCode
from museflow.domain.utils.text import validate_locales


@dataclass(frozen=True, kw_only=True)
class EnrichTracksConfigInput:
    fields: frozenset[EnrichField] = frozenset(EnrichField)
    # Only these tracks, e.g. a fixed sample to compare models on; all the user's tracks when None
    fingerprints: list[str] | None = None
    force: bool = False
    batch_size: int = 200
    limit: int | None = None
    # Each failed batch may still be billed (e.g. truncated replies): stop after this many failures in a row
    max_consecutive_failures: int = 3


class EnrichTracksJobInput(BaseModel):
    """What an enrichment job runs on, kept as its input: the fields to fill on the tracks that lack them.

    A Pydantic model: the API validates it as the request body, the job keeps it as JSON (`model_dump(mode="json")`),
    read back with `model_validate`. Neither `force` nor `limit`: a try that resumes after its worker died finds the
    tracks left to enrich from the fields still missing, which both would defeat, paying the tracks done again.
    """

    model_config = ConfigDict(frozen=True)

    fields: frozenset[EnrichField] = Field(
        default=EnrichTracksConfigInput.fields,
        min_length=1,
        description="The fields to fill on the tracks that lack them, all by default",
    )

    @field_serializer("fields")
    def _serialize_fields(self, fields: frozenset[EnrichField]) -> list[EnrichField]:
        # A set has no order: sorted, the JSON kept stays the same from one run to the next
        return sorted(fields)


class EnrichmentEntryInput(BaseModel):
    fingerprint: str

    genres: list[GenreTag] = []
    moods: list[MoodTag] = []
    locales: list[LocaleCode] | None = None

    @field_validator("locales", mode="before")
    @classmethod
    def _filter_locales(cls, value: object) -> list[str] | None:
        return validate_locales(value)

    @field_validator("genres", mode="before")
    @classmethod
    def _filter_genres(cls, value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        return [g for g in value if isinstance(g, str) and g in GenreTag]

    @field_validator("moods", mode="before")
    @classmethod
    def _filter_moods(cls, value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        return [m for m in value if isinstance(m, str) and m in MoodTag]
