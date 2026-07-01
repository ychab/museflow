import pytest

from museflow.domain.entities.taste import TasteProfile
from museflow.domain.enums import DiscoveryFocus
from museflow.infrastructure.adapters.advisors.gemini.client import GeminiAdvisorAdapter


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
