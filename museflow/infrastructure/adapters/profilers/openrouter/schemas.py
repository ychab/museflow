from pydantic import BaseModel
from pydantic import Field
from pydantic import field_validator

from museflow.domain.const import GENRE_MACRO_TAGS
from museflow.domain.const import GENRE_MESO_TAGS
from museflow.domain.const import GENRE_MICRO_TAGS
from museflow.domain.enums import GenreTag
from museflow.domain.enums import MoodTag
from museflow.infrastructure.adapters.common.llm.json_schema import JsonSchemaProperty

_VALID_IDENTITY_KEYS: frozenset[str] = frozenset(t.value for t in GenreTag) | frozenset(m.value for m in MoodTag)

# One weight list per vocabulary tier: a single enum of every tag (178) is too large for some providers (Gemini)
_WEIGHT_TIERS: dict[str, list[str]] = {
    "genre_macro": [t.value for t in GENRE_MACRO_TAGS],
    "genre_meso": [t.value for t in GENRE_MESO_TAGS],
    "genre_micro": [t.value for t in GENRE_MICRO_TAGS],
    "mood": [m.value for m in MoodTag],
}

_MOOD_ENUM: list[str] = _WEIGHT_TIERS["mood"]

# Models return weights with up to 16 decimals: noise that costs prompt tokens at each later step
_WEIGHT_DECIMALS = 3

# Built in reverse so the first tier wins for a tag listed in two ("romantic" is a meso genre and a mood)
_TIER_BY_TAG: dict[str, str] = {tag: tier for tier, tags in reversed(_WEIGHT_TIERS.items()) for tag in tags}


def _weighted_tags() -> JsonSchemaProperty:
    """A `{tag: weight}` map, as one list of `{key, value}` per tier since strict mode forbids free-form keys."""
    return JsonSchemaProperty.object(
        {
            tier: JsonSchemaProperty.array(
                JsonSchemaProperty.object(
                    {"key": JsonSchemaProperty.enum_string(tags), "value": JsonSchemaProperty.number()}
                )
            )
            for tier, tags in _WEIGHT_TIERS.items()
        }
    )


def split_weights(weights: dict[str, float]) -> dict[str, list[dict[str, str | float]]]:
    """Groups a `{tag: weight}` map by tier, the shape the response schema asks the model to write."""
    tiers: dict[str, list[dict[str, str | float]]] = {tier: [] for tier in _WEIGHT_TIERS}
    for key, value in weights.items():
        if key in _TIER_BY_TAG:
            tiers[_TIER_BY_TAG[key]].append({"key": key, "value": value})
    return tiers


class TechnicalFingerprint(BaseModel):
    energy: float
    acousticness: float
    rhythmic_complexity: float
    atmospheric: float
    instrumentalness: float


class TasteEra(BaseModel):
    era_label: str
    time_range: str
    technical_fingerprint: TechnicalFingerprint
    dominant_moods: list[str]

    @field_validator("dominant_moods", mode="before")
    @classmethod
    def _filter_moods(cls, v: object) -> list[str]:
        if not isinstance(v, list):
            return []
        return [m for m in v if isinstance(m, str) and m in MoodTag._value2member_map_]


class TasteProfileResponse(BaseModel):
    taste_timeline: list[TasteEra]
    core_identity: dict[str, float]
    current_vibe: dict[str, float]

    personality_archetype: str | None = None
    life_phase_insights: list[str] = Field(default_factory=list)

    musical_identity_summary: str | None = None
    behavioral_traits: dict[str, float] = Field(default_factory=dict)
    discovery_style: str | None = None

    @field_validator("core_identity", "current_vibe", mode="before")
    @classmethod
    def _from_weighted_tiers(cls, v: object) -> dict[str, float]:
        if not isinstance(v, dict) or not all(isinstance(items, list) for items in v.values()):
            raise ValueError(f"expected an object of {{key, value}} lists per tier, got {type(v).__name__}")
        weights = {
            item["key"]: round(item["value"], _WEIGHT_DECIMALS)
            for items in v.values()
            for item in items
            if item["key"] in _VALID_IDENTITY_KEYS
        }
        return {key: weight for key, weight in weights.items() if weight}  # a zero weight carries no signal

    @field_validator("behavioral_traits", mode="before")
    @classmethod
    def _null_traits(cls, v: object) -> object:
        return {} if v is None else v  # null until the reflection step


TASTE_PROFILE_SCHEMA = JsonSchemaProperty.object(
    {
        "taste_timeline": JsonSchemaProperty.array(
            JsonSchemaProperty.object(
                {
                    "era_label": JsonSchemaProperty.string(),
                    "time_range": JsonSchemaProperty.string(),
                    "technical_fingerprint": JsonSchemaProperty.object(
                        {
                            "energy": JsonSchemaProperty.number(),
                            "acousticness": JsonSchemaProperty.number(),
                            "rhythmic_complexity": JsonSchemaProperty.number(),
                            "atmospheric": JsonSchemaProperty.number(),
                            "instrumentalness": JsonSchemaProperty.number(),
                        }
                    ),
                    "dominant_moods": JsonSchemaProperty.array(JsonSchemaProperty.enum_string(_MOOD_ENUM)),
                }
            )
        ),
        "core_identity": _weighted_tags(),
        "current_vibe": _weighted_tags(),
        "personality_archetype": JsonSchemaProperty.string(nullable=True),
        "life_phase_insights": JsonSchemaProperty.array(JsonSchemaProperty.string()),
        "musical_identity_summary": JsonSchemaProperty.string(nullable=True),
        "behavioral_traits": JsonSchemaProperty.object(
            {
                "openness": JsonSchemaProperty.number(),
                "adventurousness": JsonSchemaProperty.number(),
                "nostalgia_bias": JsonSchemaProperty.number(),
                "rhythmic_dependency": JsonSchemaProperty.number(),
            },
            nullable=True,
        ),
        "discovery_style": JsonSchemaProperty.string(nullable=True),
    }
)
