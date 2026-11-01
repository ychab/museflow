from pydantic import BaseModel
from pydantic import Field
from pydantic import field_validator

from museflow.domain.const import GENRE_MACRO_TAGS
from museflow.domain.const import GENRE_MESO_TAGS
from museflow.domain.const import GENRE_MICRO_TAGS
from museflow.domain.enums import EnrichField
from museflow.domain.enums import MoodTag
from museflow.domain.types import LocaleCode
from museflow.domain.utils.text import validate_locales
from museflow.infrastructure.adapters.common.llm.json_schema import JsonSchemaProperty


def build_enrichment_schema(fields: frozenset[EnrichField]) -> JsonSchemaProperty:
    properties: dict[str, JsonSchemaProperty] = {"track_index": JsonSchemaProperty.integer()}

    if EnrichField.GENRE in fields:
        # One field per tier: the whole vocabulary in a single enum is too large for some providers (Gemini)
        properties["genre_macro"] = JsonSchemaProperty.enum_string([g.value for g in GENRE_MACRO_TAGS])
        properties["genre_meso"] = JsonSchemaProperty.enum_string([g.value for g in GENRE_MESO_TAGS])
        properties["genre_micro"] = JsonSchemaProperty.enum_string([g.value for g in GENRE_MICRO_TAGS], nullable=True)
    if EnrichField.MOOD in fields:
        properties["moods"] = JsonSchemaProperty.array(
            items=JsonSchemaProperty.enum_string([m.value for m in MoodTag])
        )
    if EnrichField.LOCALE in fields:
        properties["locales"] = JsonSchemaProperty.array(items=JsonSchemaProperty.string())

    return JsonSchemaProperty.object(
        {"enriched_tracks": JsonSchemaProperty.array(JsonSchemaProperty.object(properties))}
    )


class EnrichedTrack(BaseModel):
    track_index: int
    genre_macro: str | None = None
    genre_meso: str | None = None
    genre_micro: str | None = None
    moods: list[str] = Field(default_factory=list)
    locales: list[LocaleCode] | None = None

    @field_validator("locales", mode="before")
    @classmethod
    def _filter_locales(cls, v: object) -> list[str] | None:
        return validate_locales(v)

    @property
    def genres(self) -> list[str]:
        return [g for g in (self.genre_macro, self.genre_meso, self.genre_micro) if g]


class EnrichmentResponse(BaseModel):
    enriched_tracks: list[EnrichedTrack]
