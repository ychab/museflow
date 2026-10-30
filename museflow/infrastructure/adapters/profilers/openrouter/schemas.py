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

_ALL_GENRE_ENUM: list[str] = (
    [t.value for t in GENRE_MACRO_TAGS] + [t.value for t in GENRE_MESO_TAGS] + [t.value for t in GENRE_MICRO_TAGS]
)
_ALL_MOOD_ENUM: list[str] = [m.value for m in MoodTag]


def _weighted_tags() -> JsonSchemaProperty:
    """A `{tag: weight}` map, expressed as a list of `{key, value}` since strict mode forbids free-form keys."""
    return JsonSchemaProperty.array(
        JsonSchemaProperty.object(
            {
                "key": JsonSchemaProperty.enum_string(_ALL_GENRE_ENUM + _ALL_MOOD_ENUM),
                "value": JsonSchemaProperty.number(),
            }
        )
    )


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
    def _from_key_value_list(cls, v: object) -> dict[str, float]:
        if not isinstance(v, list):
            raise ValueError(f"expected a list of {{key, value}} objects, got {type(v).__name__}")
        return {item["key"]: item["value"] for item in v if item["key"] in _VALID_IDENTITY_KEYS}

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
                    "dominant_moods": JsonSchemaProperty.array(JsonSchemaProperty.enum_string(_ALL_MOOD_ENUM)),
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
