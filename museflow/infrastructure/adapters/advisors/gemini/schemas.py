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


GEMINI_DISCOVERY_STRATEGY_CONFIG = GeminiGenerationConfig(
    responseMimeType="application/json",
    responseSchema=GeminiSchemaProperty.object(
        properties={
            "reasoning": GeminiSchemaProperty.string(),
            "strategy_label": GeminiSchemaProperty.string(),
            "recommended_tracks": GeminiSchemaProperty.array(
                items=GeminiSchemaProperty.object(
                    properties={
                        "name": GeminiSchemaProperty.string(),
                        "artists": GeminiSchemaProperty.array(items=GeminiSchemaProperty.string()),
                        "score": GeminiSchemaProperty.number(),
                    },
                    required=["name", "artists", "score"],
                )
            ),
            "search_queries": GeminiSchemaProperty.array(items=GeminiSchemaProperty.string()),
            "suggested_playlist_name": GeminiSchemaProperty.string(),
        },
        required=["reasoning", "strategy_label", "recommended_tracks", "search_queries", "suggested_playlist_name"],
    ),
)


class GeminiDiscoveryStrategyContent(BaseModel):
    reasoning: str
    strategy_label: str
    recommended_tracks: list[GeminiSuggestedTrack]
    search_queries: list[str]
    suggested_playlist_name: str
