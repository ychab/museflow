from collections.abc import AsyncGenerator

import pytest

from museflow.application.ports.advisors.agent import AdvisorPort
from museflow.domain.entities.taste import TasteProfile
from museflow.domain.enums import DiscoveryFocus
from museflow.infrastructure.entrypoints.cli.dependencies import get_advisor


@pytest.mark.openrouter_live
class TestOpenRouterAdvisorLive:
    """
    Live integration tests against the real OpenRouter API.

    These tests verify that the OpenRouter API contract hasn't changed and that our
    Client Adapter correctly handles real-world responses.

    Requirements:
        - OPENROUTER_API_KEY set in env or .env file.
        - Network access to openrouter.ai.

    Warning:
        These tests are slow, depend on external services and spend real money. They are NOT run by default.

    To run:
        OPENROUTER_API_KEY=<KEY> uv run pytest ./tests/integration/live/openrouter --openrouter-live --no-cov
    """

    @pytest.fixture
    async def openrouter_advisor_live(self) -> AsyncGenerator[AdvisorPort]:
        async with get_advisor() as client:
            yield client

    async def test__get_discovery_strategy(
        self,
        openrouter_advisor_live: AdvisorPort,
        taste_profile: TasteProfile,
    ) -> None:
        strategy = await openrouter_advisor_live.get_discovery_strategy(
            profile=taste_profile,
            focus=DiscoveryFocus.EXPANSION,
            advisor_limit=5,
        )
        assert strategy.strategy_label
        assert len(strategy.recommended_tracks) > 0
