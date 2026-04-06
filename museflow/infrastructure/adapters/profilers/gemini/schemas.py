from pydantic import BaseModel

from museflow.infrastructure.adapters.common.gemini.schemas import GeminiGenerationConfig
from museflow.infrastructure.adapters.common.gemini.schemas import GeminiSchemaProperty


class GeminiTasteEra(BaseModel):
    era_label: str
    time_range: str
    technical_fingerprint: dict[str, float]
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
                    "technical_fingerprint": GeminiSchemaProperty(
                        type="object", additionalProperties=GeminiSchemaProperty.number()
                    ),
                    "dominant_moods": GeminiSchemaProperty.array(items=GeminiSchemaProperty.string()),
                },
            ),
        ),
        "core_identity": GeminiSchemaProperty(type="object", additionalProperties=GeminiSchemaProperty.number()),
        "current_vibe": GeminiSchemaProperty(type="object", additionalProperties=GeminiSchemaProperty.number()),
        "personality_archetype": GeminiSchemaProperty.string(),
        "life_phase_insights": GeminiSchemaProperty.array(items=GeminiSchemaProperty.string()),
    },
)

GEMINI_TASTE_PROFILE_CONFIG = GeminiGenerationConfig(
    responseMimeType="application/json",
    responseSchema=GEMINI_TASTE_PROFILE_RESPONSE_SCHEMA,
)
