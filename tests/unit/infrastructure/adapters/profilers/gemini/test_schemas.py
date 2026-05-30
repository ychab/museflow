from pydantic import ValidationError

import pytest

from museflow.infrastructure.adapters.profilers.gemini.schemas import GeminiTasteProfileContent


class TestGeminiTasteProfileContent:
    @pytest.fixture
    def payload(self) -> dict[object, object]:
        return {
            "taste_timeline": [],
            "core_identity": [{"key": "indie rock", "value": 0.8}],
            "current_vibe": [{"key": "indie rock", "value": 0.9}],
            "producer_affinities": [],
        }

    def test__from_key_value_list__rejects_dict(self, payload: dict[object, object]) -> None:
        with pytest.raises(ValidationError):
            GeminiTasteProfileContent.model_validate({**payload, "core_identity": {"indie rock": 0.8}})

    def test__from_key_value_list__none_returns_empty_dict(self, payload: dict[object, object]) -> None:
        content = GeminiTasteProfileContent.model_validate({**payload, "producer_affinities": None})
        assert content.producer_affinities == {}
