from pydantic import ValidationError

import pytest

from museflow.infrastructure.adapters.advisors.openrouter.schemas import DISCOVERY_STRATEGY_SCHEMA
from museflow.infrastructure.adapters.advisors.openrouter.schemas import SuggestedTrack


class TestSuggestedTrack:
    def test__parse__multiple_artists(self) -> None:
        track = SuggestedTrack.model_validate({"name": "Song", "artists": ["A", "B"], "score": 0.5})
        assert track.artists == ["A", "B"]

    @pytest.mark.parametrize(
        "data",
        [
            pytest.param({"name": "", "artists": ["A"], "score": 0.5}, id="empty_name"),
            pytest.param({"name": "Song", "artists": [], "score": 0.5}, id="no_artist"),
        ],
    )
    def test__parse__invalid(self, data: dict[str, object]) -> None:
        with pytest.raises(ValidationError):
            SuggestedTrack.model_validate(data)


class TestDiscoveryStrategySchema:
    def test__strict__all_properties_required(self) -> None:
        assert DISCOVERY_STRATEGY_SCHEMA.properties is not None
        assert DISCOVERY_STRATEGY_SCHEMA.required == list(DISCOVERY_STRATEGY_SCHEMA.properties)
        assert DISCOVERY_STRATEGY_SCHEMA.additionalProperties is False
