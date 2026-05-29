from pydantic import BaseModel
from pydantic import field_validator

from museflow.infrastructure.adapters.common.gemini.schemas import GeminiGenerationConfig
from museflow.infrastructure.adapters.common.gemini.schemas import GeminiSchemaProperty


class GeminiTechnicalFingerprint(BaseModel):
    energy: float
    acousticness: float
    rhythmic_complexity: float
    atmospheric: float
    instrumentalness: float


class GeminiTasteEra(BaseModel):
    era_label: str
    time_range: str
    technical_fingerprint: GeminiTechnicalFingerprint
    dominant_moods: list[str]


class GeminiTasteProfileContent(BaseModel):
    taste_timeline: list[GeminiTasteEra]
    core_identity: dict[str, float]
    current_vibe: dict[str, float]

    personality_archetype: str | None = None
    life_phase_insights: list[str] = []

    musical_identity_summary: str | None = None
    behavioral_traits: dict[str, float] = {}
    discovery_style: str | None = None

    @field_validator("core_identity", "current_vibe", mode="before")
    @classmethod
    def _from_key_value_list(cls, v: object) -> dict[str, float]:
        if not isinstance(v, list):
            raise ValueError(f"expected a list of {{key, value}} objects, got {type(v).__name__}")
        return {item["key"]: item["value"] for item in v}


GEMINI_TASTE_PROFILE_RESPONSE_SCHEMA = GeminiSchemaProperty.object(
    properties={
        "taste_timeline": GeminiSchemaProperty.array(
            items=GeminiSchemaProperty.object(
                properties={
                    "era_label": GeminiSchemaProperty.string(),
                    "time_range": GeminiSchemaProperty.string(),
                    "technical_fingerprint": GeminiSchemaProperty.object(
                        properties={
                            "energy": GeminiSchemaProperty.number(),
                            "acousticness": GeminiSchemaProperty.number(),
                            "rhythmic_complexity": GeminiSchemaProperty.number(),
                            "atmospheric": GeminiSchemaProperty.number(),
                            "instrumentalness": GeminiSchemaProperty.number(),
                        },
                        required=["energy", "acousticness", "rhythmic_complexity", "atmospheric", "instrumentalness"],
                    ),
                    "dominant_moods": GeminiSchemaProperty.array(items=GeminiSchemaProperty.string()),
                },
                required=["era_label", "time_range", "technical_fingerprint", "dominant_moods"],
            ),
        ),
        "core_identity": GeminiSchemaProperty.array(
            items=GeminiSchemaProperty.object(
                properties={
                    "key": GeminiSchemaProperty.string(),
                    "value": GeminiSchemaProperty.number(),
                },
                required=["key", "value"],
            )
        ),
        "current_vibe": GeminiSchemaProperty.array(
            items=GeminiSchemaProperty.object(
                properties={
                    "key": GeminiSchemaProperty.string(),
                    "value": GeminiSchemaProperty.number(),
                },
                required=["key", "value"],
            )
        ),
        "personality_archetype": GeminiSchemaProperty.string(),
        "life_phase_insights": GeminiSchemaProperty.array(items=GeminiSchemaProperty.string()),
        "musical_identity_summary": GeminiSchemaProperty.string(),
        "behavioral_traits": GeminiSchemaProperty.object(
            properties={
                "openness": GeminiSchemaProperty.number(),
                "adventurousness": GeminiSchemaProperty.number(),
                "nostalgia_bias": GeminiSchemaProperty.number(),
                "rhythmic_dependency": GeminiSchemaProperty.number(),
            },
            required=["openness", "adventurousness", "nostalgia_bias", "rhythmic_dependency"],
        ),
        "discovery_style": GeminiSchemaProperty.string(),
    },
    required=[
        "taste_timeline",
        "core_identity",
        "current_vibe",
        "life_phase_insights",
        "personality_archetype",
        "behavioral_traits",
        "musical_identity_summary",
    ],
)

GEMINI_TASTE_PROFILE_CONFIG = GeminiGenerationConfig(
    responseMimeType="application/json",
    responseSchema=GEMINI_TASTE_PROFILE_RESPONSE_SCHEMA,
)
