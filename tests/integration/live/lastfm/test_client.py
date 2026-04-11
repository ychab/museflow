from collections.abc import AsyncGenerator

import pytest

from museflow.application.ports.advisors.similar import AdvisorSimilarPort
from museflow.domain.entities.music import TrackSuggested
from museflow.infrastructure.entrypoints.cli.dependencies import get_lastfm_similar_advisor


@pytest.mark.lastfm_live
class TestLastfmAdvisorLive:
    """
    Live integration tests against the real Last.fm API.

    These tests verify that the Last.fm API contract hasn't changed and that our
    Client Adapter correctly handles real-world responses.

    Requirements:
        - LASTFM_CLIENT_API_KEY and LASTFM_CLIENT_SECRET set in env or .env file.
        - Network access to ws.audioscrobbler.com.

    Warning:
        These tests are slow and depend on external services. They are NOT run by default.

    To run:
        LASTFM_CLIENT_API_KEY=<KEY> LASTFM_CLIENT_SECRET=<SECRET> uv run pytest ./tests/integration/live/lastfm --lastfm-live --no-cov
    """

    @pytest.fixture
    async def lastfm_advisor_live(self) -> AsyncGenerator[AdvisorSimilarPort]:
        async with get_lastfm_similar_advisor() as client:
            yield client

    async def test__get_similar_tracks(self, lastfm_advisor_live: AdvisorSimilarPort) -> None:
        results: list[TrackSuggested] = await lastfm_advisor_live.get_similar_tracks(
            artist_name="Radiohead",
            track_name="Creep",
            limit=5,
        )
        assert len(results) > 0
        for track in results:
            assert track.name
            assert len(track.artists) > 0
            assert 0.0 <= track.score <= 1.0
