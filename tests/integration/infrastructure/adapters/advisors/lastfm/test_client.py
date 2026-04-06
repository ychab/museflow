import json
import logging
from typing import Any

import pytest

from museflow.infrastructure.adapters.advisors.lastfm.client import LastFmAdvisorAdapter

from tests import ASSETS_DIR
from tests.integration.utils.wiremock import WireMockContext


@pytest.mark.wiremock("lastfm")
class TestLastFmAdvisorAdapter:
    @pytest.fixture
    def wiremock_response(self, request: pytest.FixtureRequest) -> dict[str, Any]:
        filename = getattr(request, "param", "")
        filepath = ASSETS_DIR / "wiremock" / "lastfm" / "__files" / f"{filename}.json"
        return json.loads(filepath.read_text())

    async def test__get_similar_tracks__nominal(self, lastfm_advisor: LastFmAdvisorAdapter) -> None:
        tracks_suggested = await lastfm_advisor.get_similar_tracks(
            artist_name="dummy-artist",
            track_name="dummy-track",
            limit=20,
        )
        assert len(tracks_suggested) == 19

        track_suggested = tracks_suggested[0]
        assert track_suggested.name == "Mi Pueblo"
        assert track_suggested.artists == ["Grupo Niche"]
        assert track_suggested.advisor_id == "2ced3803-b87a-319f-9926-0388b20608be"
        assert track_suggested.score == 1.0

    @pytest.mark.parametrize("wiremock_response", ["tracks_similar_error"], indirect=["wiremock_response"])
    async def test__get_similar_tracks__error(
        self,
        lastfm_advisor: LastFmAdvisorAdapter,
        wiremock_response: dict[str, Any],
        lastfm_wiremock: WireMockContext,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        artist_name = "dummy-artist"
        track_name = "dummy-track"

        lastfm_wiremock.create_mapping(
            method="GET",
            url_path="/",
            status=200,
            query_params={
                "method": "track.getSimilar",
            },
            json_body=wiremock_response,
        )

        with caplog.at_level(logging.DEBUG):
            tracks_suggested = await lastfm_advisor.get_similar_tracks(
                artist_name=artist_name,
                track_name=track_name,
            )

        assert len(tracks_suggested) == 0
        assert (
            f"Error occurred while fetching similar tracks for artist:'{artist_name}' and track:'{track_name}' with error: 6 and message: Track not found"
            in caplog.text
        )
