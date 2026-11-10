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
        "suggested_playlist_name": JsonSchemaProperty.string(),
    }
)


class SuggestedArtist(BaseModel):
    name: str = Field(..., min_length=1)
    sound: str
    score: float


class DiscoveryArtistsResponse(BaseModel):
    reasoning: str
    strategy_label: str
    recommended_artists: list[SuggestedArtist]
    suggested_playlist_name: str


DISCOVERY_ARTISTS_SCHEMA = JsonSchemaProperty.object(
    {
        "reasoning": JsonSchemaProperty.string(),
        "strategy_label": JsonSchemaProperty.string(),
        "recommended_artists": JsonSchemaProperty.array(
            JsonSchemaProperty.object(
                {
                    "name": JsonSchemaProperty.string(),
                    "sound": JsonSchemaProperty.string(),
                    "score": JsonSchemaProperty.number(),
                }
            )
        ),
        "suggested_playlist_name": JsonSchemaProperty.string(),
    }
)


class PickedTrack(BaseModel):
    id: str
    score: float


class DiscoveryPicksResponse(BaseModel):
    picks: list[PickedTrack]


DISCOVERY_PICKS_SCHEMA = JsonSchemaProperty.object(
    {
        "picks": JsonSchemaProperty.array(
            JsonSchemaProperty.object(
                {
                    "id": JsonSchemaProperty.string(),
                    "score": JsonSchemaProperty.number(),
                }
            )
        ),
    }
)
