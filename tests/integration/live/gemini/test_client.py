from collections.abc import AsyncGenerator

import pytest

from museflow.application.ports.advisors.client import AdvisorClientPort
from museflow.domain.entities.music import TrackSuggested
from museflow.infrastructure.entrypoints.cli.dependencies import get_gemini_client


@pytest.mark.gemini_live
class TestGeminiClientLive:
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
    async def gemini_client_live(self) -> AsyncGenerator[AdvisorClientPort]:
        async with get_gemini_client() as client:
            yield client

    async def test__get_similar_tracks(self, gemini_client_live: AdvisorClientPort) -> None:
        results: list[TrackSuggested] = await gemini_client_live.get_similar_tracks(
            artist_name="Radiohead",
            track_name="Creep",
            limit=5,
        )
        assert len(results) > 0
        for track in results:
            assert track.name
            assert len(track.artists) > 0
            assert 0.0 <= track.score <= 1.0
