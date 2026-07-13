from typing import Annotated

from pydantic import BaseModel
from pydantic import Field
from pydantic.functional_validators import BeforeValidator

from museflow.domain.enums import EnrichField
from museflow.domain.types import LocaleCode
from museflow.domain.utils.text import validate_locale
from museflow.infrastructure.adapters.common.gemini.schemas import GeminiGenerationConfig
from museflow.infrastructure.adapters.common.gemini.schemas import GeminiSchemaProperty


def build_enrichment_config(fields: frozenset[EnrichField]) -> GeminiGenerationConfig:
    properties: dict[str, GeminiSchemaProperty] = {"track_index": GeminiSchemaProperty.number()}
    required = ["track_index"]

    if EnrichField.GENRE in fields:
        properties["genres"] = GeminiSchemaProperty.array(items=GeminiSchemaProperty.string())
        required.append("genres")
    if EnrichField.MOOD in fields:
        properties["moods"] = GeminiSchemaProperty.array(items=GeminiSchemaProperty.string())
        required.append("moods")
    if EnrichField.LOCALE in fields:
        properties["locale"] = GeminiSchemaProperty.string()

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
    locale: Annotated[LocaleCode | None, BeforeValidator(validate_locale)] = None


class GeminiEnrichmentResponse(BaseModel):
    enriched_tracks: list[GeminiEnrichedTrack]
