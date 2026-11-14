from typing import Final

from pydantic import BaseModel
from pydantic import Field

from museflow.infrastructure.adapters.common.llm.json_schema import JsonSchemaProperty


class SuggestedArtist(BaseModel):
    name: str = Field(..., min_length=1)
    sound: str
    score: float
    # Required by the strict schema; a model that leaves it out asks for no artist's own tracks.
    requested: bool = False


class DiscoveryArtistsResponse(BaseModel):
    reasoning: str
    strategy_label: str
    recommended_artists: list[SuggestedArtist]
    suggested_playlist_name: str


DISCOVERY_ARTISTS_SCHEMA: Final[JsonSchemaProperty] = JsonSchemaProperty.object(
    {
        "reasoning": JsonSchemaProperty.string(),
        "strategy_label": JsonSchemaProperty.string(),
        "recommended_artists": JsonSchemaProperty.array(
            JsonSchemaProperty.object(
                {
                    "name": JsonSchemaProperty.string(),
                    "sound": JsonSchemaProperty.string(),
                    "score": JsonSchemaProperty.number(),
                    "requested": JsonSchemaProperty.boolean(),
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


DISCOVERY_PICKS_SCHEMA: Final[JsonSchemaProperty] = JsonSchemaProperty.object(
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
