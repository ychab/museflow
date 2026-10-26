from pydantic import BaseModel
from pydantic import Field
from pydantic import field_validator

from museflow.domain.enums import EnrichField
from museflow.domain.enums import GenreTag
from museflow.domain.enums import MoodTag
from museflow.domain.types import LocaleCode
from museflow.domain.utils.text import validate_locales
from museflow.infrastructure.adapters.common.gemini.schemas import GeminiGenerationConfig
from museflow.infrastructure.adapters.common.gemini.schemas import GeminiSchemaProperty


def build_enrichment_config(fields: frozenset[EnrichField]) -> GeminiGenerationConfig:
    properties: dict[str, GeminiSchemaProperty] = {"track_index": GeminiSchemaProperty.number()}
    required = ["track_index"]

    if EnrichField.GENRE in fields:
        properties["genres"] = GeminiSchemaProperty.array(
            items=GeminiSchemaProperty.enum_string([g.value for g in GenreTag])
        )
        required.append("genres")
    if EnrichField.MOOD in fields:
        properties["moods"] = GeminiSchemaProperty.array(
            items=GeminiSchemaProperty.enum_string([m.value for m in MoodTag])
        )
        required.append("moods")
    if EnrichField.LOCALE in fields:
        properties["locales"] = GeminiSchemaProperty.array(items=GeminiSchemaProperty.string())
        required.append("locales")

    return GeminiGenerationConfig(
        responseMimeType="application/json",
        responseSchema=GeminiSchemaProperty.object(
            properties={
                "enriched_tracks": GeminiSchemaProperty.array(
                    items=GeminiSchemaProperty.object(
                        properties=properties,
                        required=required,
                    )
                )
            },
            required=["enriched_tracks"],
        ),
    )


class GeminiEnrichedTrack(BaseModel):
    track_index: int
    genres: list[str] = Field(default_factory=list)
    moods: list[str] = Field(default_factory=list)
    locales: list[LocaleCode] | None = None

    @field_validator("locales", mode="before")
    @classmethod
    def _filter_locales(cls, v: object) -> list[str] | None:
        return validate_locales(v)


class GeminiEnrichmentResponse(BaseModel):
    enriched_tracks: list[GeminiEnrichedTrack]
