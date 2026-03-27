from collections.abc import Iterable
from unittest import mock

import pytest
from pytest_httpx import HTTPXMock

from museflow.domain.exceptions import SimilarTrackResponseException
from museflow.infrastructure.adapters.advisors.gemini.client import GeminiClientAdapter


class TestGeminiClientAdapter:
    @pytest.fixture
    def mock_tenacity_sleep(self) -> Iterable[None]:
        retry_controller = GeminiClientAdapter.make_api_call.retry  # type: ignore[attr-defined]
        original_sleep = retry_controller.sleep

        retry_controller.sleep = mock.AsyncMock(return_value=None)
        yield
        retry_controller.sleep = original_sleep

    async def test__get_similar_tracks__nominal(
        self,
        gemini_client: GeminiClientAdapter,
        httpx_mock: HTTPXMock,
    ) -> None:
        httpx_mock.add_response(
            url="https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
            method="POST",
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": '{"tracks": [{"name": "Mi Pueblo", "artists": ["Grupo Niche"], "score": 1.0}]}'
                                }
                            ],
                            "role": "model",
                        }
                    }
                ]
            },
        )

        tracks = await gemini_client.get_similar_tracks(artist_name="Grupo Niche", track_name="La Negra No Quiere")

        assert len(tracks) == 1
        assert tracks[0].name == "Mi Pueblo"
        assert tracks[0].artists == ["Grupo Niche"]
        assert tracks[0].advisor_id is None
        assert tracks[0].score == pytest.approx(1.0)

    async def test__get_similar_tracks__empty_candidates(
        self,
        gemini_client: GeminiClientAdapter,
        httpx_mock: HTTPXMock,
    ) -> None:
        httpx_mock.add_response(
            url="https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
            method="POST",
            json={"candidates": []},
        )

        tracks = await gemini_client.get_similar_tracks(artist_name="Artist", track_name="Track")

        assert tracks == []

    async def test__get_similar_tracks__invalid_json_raises(
        self,
        gemini_client: GeminiClientAdapter,
        httpx_mock: HTTPXMock,
    ) -> None:
        httpx_mock.add_response(
            url="https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
            method="POST",
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [{"text": "not-valid-json{{{"}],
                            "role": "model",
                        }
                    }
                ]
            },
        )

        with pytest.raises(SimilarTrackResponseException):
            await gemini_client.get_similar_tracks(artist_name="Artist", track_name="Track")

    async def test__get_similar_tracks__invalid_schema_raises(
        self,
        gemini_client: GeminiClientAdapter,
        httpx_mock: HTTPXMock,
    ) -> None:
        httpx_mock.add_response(
            url="https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
            method="POST",
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [{"text": '{"wrong_key": []}'}],
                            "role": "model",
                        }
                    }
                ]
            },
        )

        with pytest.raises(SimilarTrackResponseException):
            await gemini_client.get_similar_tracks(artist_name="Artist", track_name="Track")

    def test__display_name(self, gemini_client: GeminiClientAdapter) -> None:
        assert gemini_client.display_name == "Gemini"
