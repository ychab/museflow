from pydantic import BaseModel
from pydantic import Field
from pydantic import field_validator

from museflow.domain.enums import EnrichField
from museflow.domain.enums import GenreTag
from museflow.domain.enums import MoodTag
from museflow.domain.types import LocaleCode
from museflow.domain.utils.text import validate_locales
from museflow.infrastructure.adapters.common.llm.json_schema import JsonSchemaProperty


def build_enrichment_schema(fields: frozenset[EnrichField]) -> JsonSchemaProperty:
    properties: dict[str, JsonSchemaProperty] = {"track_index": JsonSchemaProperty.integer()}

    if EnrichField.GENRE in fields:
        properties["genres"] = JsonSchemaProperty.array(
            items=JsonSchemaProperty.enum_string([g.value for g in GenreTag])
        )
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
    genres: list[str] = Field(default_factory=list)
    moods: list[str] = Field(default_factory=list)
    locales: list[LocaleCode] | None = None

    @field_validator("locales", mode="before")
    @classmethod
    def _filter_locales(cls, v: object) -> list[str] | None:
        return validate_locales(v)


class EnrichmentResponse(BaseModel):
    enriched_tracks: list[EnrichedTrack]
