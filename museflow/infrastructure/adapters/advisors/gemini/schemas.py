from pydantic import BaseModel
from pydantic import Field

from museflow.infrastructure.adapters.common.gemini.schemas import GeminiGenerationConfig
from museflow.infrastructure.adapters.common.gemini.schemas import GeminiSchemaProperty

GEMINI_TRACK_SUGGESTIONS_CONFIG = GeminiGenerationConfig(
    responseMimeType="application/json",
    responseSchema=GeminiSchemaProperty.object(
        properties={
            "tracks": GeminiSchemaProperty.array(
                items=GeminiSchemaProperty.object(
                    properties={
                        "name": GeminiSchemaProperty.string(),
                        "artists": GeminiSchemaProperty.array(items=GeminiSchemaProperty.string()),
                        "score": GeminiSchemaProperty.number(),
                    },
                    required=["name", "artists", "score"],
                )
            )
        },
        required=["tracks"],
    ),
)


class GeminiSuggestedTrack(BaseModel):
    name: str = Field(..., min_length=1)
    artists: list[str] = Field(..., min_length=1)
    score: float


class GeminiSuggestedTracksContent(BaseModel):
    tracks: list[GeminiSuggestedTrack]
