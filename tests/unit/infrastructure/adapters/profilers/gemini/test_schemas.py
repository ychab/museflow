from typing import Any

from pydantic import ValidationError

import pytest

from museflow.infrastructure.adapters.profilers.gemini.schemas import GeminiTasteEra
from museflow.infrastructure.adapters.profilers.gemini.schemas import GeminiTasteProfileContent

from tests.integration.factories.models.taste import TasteProfileDataFactory

_BASE_FINGERPRINT: dict[str, float] = {
    "energy": 0.5,
    "acousticness": 0.5,
    "rhythmic_complexity": 0.5,
    "atmospheric": 0.5,
    "instrumentalness": 0.5,
}

_BASE_ERA: dict[str, Any] = {
    "era_label": "Test Era",
    "time_range": "2020-2021",
    "technical_fingerprint": _BASE_FINGERPRINT,
    "dominant_moods": [],
}

_BASE_PROFILE: dict[str, Any] = {
    "taste_timeline": [_BASE_ERA],
    "core_identity": [{"key": "rock", "value": 0.8}],
    "current_vibe": [{"key": "energetic", "value": 0.6}],
    "personality_archetype": None,
    "life_phase_insights": [],
}


class TestGeminiTasteEra:
    def test__dominant_moods__keeps_valid_mood_tags(self) -> None:
        era = GeminiTasteEra.model_validate({**_BASE_ERA, "dominant_moods": ["melancholic", "energetic"]})
        assert era.dominant_moods == ["melancholic", "energetic"]

    def test__dominant_moods__filters_invalid_strings(self) -> None:
        era = GeminiTasteEra.model_validate(
            {**_BASE_ERA, "dominant_moods": ["melancholic", "ambient vibes", "energetic"]}
        )
        assert era.dominant_moods == ["melancholic", "energetic"]

    def test__dominant_moods__non_list_returns_empty(self) -> None:
        era = GeminiTasteEra.model_validate({**_BASE_ERA, "dominant_moods": "melancholic"})
        assert era.dominant_moods == []


class TestGeminiTasteProfileContent:
    def test__from_key_value_list__rejects_dict(self) -> None:
        profile = TasteProfileDataFactory.build()
        with pytest.raises(ValidationError):
            GeminiTasteProfileContent.model_validate(
                {
                    **profile,
                    "core_identity": {"indie-rock": 0.8},
                    "current_vibe": [{"key": "indie-rock", "value": 0.9}],
                }
            )

    def test__core_identity__filters_invalid_keys(self) -> None:
        content = GeminiTasteProfileContent.model_validate(
            {
                **_BASE_PROFILE,
                "core_identity": [
                    {"key": "rock", "value": 0.8},
                    {"key": "free form nonsense", "value": 0.5},
                ],
            }
        )
        assert content.core_identity == {"rock": 0.8}

    def test__current_vibe__accepts_valid_mood_key(self) -> None:
        content = GeminiTasteProfileContent.model_validate(
            {**_BASE_PROFILE, "current_vibe": [{"key": "melancholic", "value": 0.7}]}
        )
        assert content.current_vibe == {"melancholic": 0.7}

    def test__core_identity__filters_all_invalid_keys(self) -> None:
        content = GeminiTasteProfileContent.model_validate(
            {**_BASE_PROFILE, "core_identity": [{"key": "made up genre", "value": 0.9}]}
        )
        assert content.core_identity == {}
