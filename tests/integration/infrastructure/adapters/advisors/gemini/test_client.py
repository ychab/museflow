import pytest

from museflow.domain.entities.taste import TasteProfile
from museflow.domain.enums import DiscoveryFocus
from museflow.infrastructure.adapters.advisors.gemini.client import GeminiAdvisorAdapter

from tests.integration.utils.wiremock import WireMockContext


@pytest.mark.wiremock("gemini")
class TestGeminiAdvisorAdapter:
    async def test__get_discovery_strategy__nominal(
        self,
        gemini_advisor: GeminiAdvisorAdapter,
        taste_profile: TasteProfile,
    ) -> None:
        strategy = await gemini_advisor.get_discovery_strategy(
            profile=taste_profile,
            focus=DiscoveryFocus.EXPANSION,
            advisor_limit=5,
        )

        assert strategy.strategy_label == "Progressive Horizons"
        assert strategy.suggested_playlist_name == "Sonic Expansion - Progressive Horizons"
        assert strategy.search_queries == ["post-rock instrumental", "math rock progressive"]
        assert len(strategy.recommended_tracks) == 1
        assert strategy.recommended_tracks[0].name == "Mi Pueblo"
        assert strategy.recommended_tracks[0].artists == ["Grupo Niche"]
        assert strategy.recommended_tracks[0].score == pytest.approx(1.0)

    async def test__get_discovery_strategy__invalid_response_then_valid__self_heals(
        self,
        gemini_advisor: GeminiAdvisorAdapter,
        gemini_wiremock: WireMockContext,
        taste_profile: TasteProfile,
    ) -> None:
        endpoint = "/models/gemini-2.5-flash:generateContent"
        invalid_body = {"candidates": [{"content": {"parts": [{"text": '{"wrong_key": 1}'}], "role": "model"}}]}
        gemini_wiremock.create_mapping(
            method="POST",
            url_path=endpoint,
            status=200,
            json_body=invalid_body,
            priority=0,
            scenario_name="advisor-self-healing",
            required_state="Started",
            new_state="invalid-served",
        )

        strategy = await gemini_advisor.get_discovery_strategy(
            profile=taste_profile,
            focus=DiscoveryFocus.EXPANSION,
            advisor_limit=5,
        )

        assert strategy.strategy_label == "Progressive Horizons"
        assert len(strategy.recommended_tracks) == 1
