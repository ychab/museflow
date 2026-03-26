import re

import pytest
from pytest_httpx import HTTPXMock

from museflow.domain.exceptions import SimilarTrackResponseException
from museflow.infrastructure.adapters.advisors.lastfm.client import LastFmClientAdapter


class TestLastFmClientAdapter:
    async def test__get_similar_tracks__none(self, lastfm_client: LastFmClientAdapter, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            url=re.compile(f"^{re.escape(str(lastfm_client.base_url))}.*"),
            method="GET",
            json={"similartracks": {"track": []}},
        )

        tracks_suggested = await lastfm_client.get_similar_tracks(
            artist_name="dummy-artist",
            track_name="dummy-track",
            limit=20,
        )

        assert len(tracks_suggested) == 0

    async def test__get_similar_tracks__response_exception(
        self,
        lastfm_client: LastFmClientAdapter,
        httpx_mock: HTTPXMock,
    ) -> None:
        httpx_mock.add_response(
            url=re.compile(f"^{re.escape(str(lastfm_client.base_url))}.*"),
            method="GET",
            json={
                "similartracks": {
                    "track": [
                        {
                            "artist": {
                                "mbid": "5436ce22-af50-4714-addc-afd5d2efc77f",
                                "name": "Grupo Niche",
                            },
                            "match": 71.5,
                            "mbid": "2ced3803-b87a-319f-9926-0388b20608be",
                            "name": "Mi Pueblo",
                        },
                    ],
                },
            },
        )

        with pytest.raises(SimilarTrackResponseException):
            await lastfm_client.get_similar_tracks(
                artist_name="dummy-artist",
                track_name="dummy-track",
            )
