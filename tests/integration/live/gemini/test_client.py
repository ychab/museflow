from collections.abc import AsyncGenerator

import pytest

from museflow.application.ports.advisors.agent import AdvisorAgentPort
from museflow.domain.entities.taste import TasteProfile
from museflow.domain.types import DiscoveryFocus
from museflow.infrastructure.entrypoints.cli.dependencies import get_gemini_taste_advisor


@pytest.mark.gemini_live
class TestGeminiAdvisorLive:
    """
    Live integration tests against the real Gemini API.

    These tests verify that the Gemini API contract hasn't changed and that our
    Client Adapter correctly handles real-world responses.

    Requirements:
        - GEMINI_API_KEY set in env or .env file.
        - Network access to generativelanguage.googleapis.com.

    Warning:
        These tests are slow and depend on external services. They are NOT run by default.

    To run:
        GEMINI_API_KEY=<KEY> uv run pytest ./tests/integration/live/gemini --gemini-live --no-cov
    """

    @pytest.fixture
    async def gemini_advisor_live(self) -> AsyncGenerator[AdvisorAgentPort]:
        async with get_gemini_taste_advisor() as client:
            yield client

    async def test__get_discovery_strategy(
        self,
        gemini_advisor_live: AdvisorAgentPort,
        taste_profile: TasteProfile,
    ) -> None:
        strategy = await gemini_advisor_live.get_discovery_strategy(
            profile=taste_profile,
            focus=DiscoveryFocus.EXPANSION,
            similar_limit=5,
        )
        assert strategy.strategy_label
        assert len(strategy.recommended_tracks) > 0
