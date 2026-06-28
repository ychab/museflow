from pydantic import BaseModel
from pydantic import Field

from museflow.infrastructure.adapters.common.gemini.schemas import GeminiGenerationConfig
from museflow.infrastructure.adapters.common.gemini.schemas import GeminiSchemaProperty

GEMINI_ENRICHMENT_CONFIG = GeminiGenerationConfig(
    responseMimeType="application/json",
    responseSchema=GeminiSchemaProperty.object(
        properties={
            "enriched_tracks": GeminiSchemaProperty.array(
                items=GeminiSchemaProperty.object(
                    properties={
                        "track_index": GeminiSchemaProperty.number(),
                        "genres": GeminiSchemaProperty.array(items=GeminiSchemaProperty.string()),
                        "moods": GeminiSchemaProperty.array(items=GeminiSchemaProperty.string()),
                    },
                    required=["track_index", "genres", "moods"],
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


class GeminiEnrichmentResponse(BaseModel):
    enriched_tracks: list[GeminiEnrichedTrack]
