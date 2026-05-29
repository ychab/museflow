from pydantic import ValidationError

import pytest

from museflow.infrastructure.adapters.profilers.gemini.schemas import GeminiTasteProfileContent

from tests.integration.factories.models.taste import TasteProfileDataFactory


class TestGeminiTasteProfileContent:
    def test__from_key_value_list__rejects_dict(self) -> None:
        profile = TasteProfileDataFactory.build()
        with pytest.raises(ValidationError):
            GeminiTasteProfileContent.model_validate(
                {
                    **profile,
                    "core_identity": {"indie rock": 0.8},
                    "current_vibe": [{"key": "indie rock", "value": 0.9}],
                }
            )
