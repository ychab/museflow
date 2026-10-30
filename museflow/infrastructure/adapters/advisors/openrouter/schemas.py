from pydantic import BaseModel
from pydantic import Field

from museflow.infrastructure.adapters.common.llm.json_schema import JsonSchemaProperty


class SuggestedTrack(BaseModel):
    name: str = Field(..., min_length=1)
    artists: list[str] = Field(..., min_length=1)
    score: float


class DiscoveryStrategyResponse(BaseModel):
    reasoning: str
    strategy_label: str
    recommended_tracks: list[SuggestedTrack]
    search_queries: list[str]
    suggested_playlist_name: str


DISCOVERY_STRATEGY_SCHEMA = JsonSchemaProperty.object(
    {
        "reasoning": JsonSchemaProperty.string(),
        "strategy_label": JsonSchemaProperty.string(),
        "recommended_tracks": JsonSchemaProperty.array(
            JsonSchemaProperty.object(
                {
                    "name": JsonSchemaProperty.string(),
                    "artists": JsonSchemaProperty.array(JsonSchemaProperty.string()),
                    "score": JsonSchemaProperty.number(),
                }
            )
        ),
        "search_queries": JsonSchemaProperty.array(JsonSchemaProperty.string()),
        "suggested_playlist_name": JsonSchemaProperty.string(),
    }
)
