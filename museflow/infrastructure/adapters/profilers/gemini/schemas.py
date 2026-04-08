from pydantic import BaseModel

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
        "core_identity": GeminiSchemaProperty(type="object"),
        "current_vibe": GeminiSchemaProperty(type="object"),
        "personality_archetype": GeminiSchemaProperty.string(),
        "life_phase_insights": GeminiSchemaProperty.array(items=GeminiSchemaProperty.string()),
    },
    required=["taste_timeline", "core_identity", "current_vibe", "life_phase_insights"],
)

GEMINI_TASTE_PROFILE_CONFIG = GeminiGenerationConfig(
    responseMimeType="application/json",
    responseSchema=GEMINI_TASTE_PROFILE_RESPONSE_SCHEMA,
)
