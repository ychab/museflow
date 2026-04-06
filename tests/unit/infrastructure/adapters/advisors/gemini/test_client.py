from collections.abc import Iterable
from unittest import mock

import httpx
from httpx import codes

import pytest
from pytest_httpx import HTTPXMock

from museflow.domain.exceptions import AdvisorRateLimitExceeded
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

    async def test__get_similar_tracks__rate_limit_exhausted(
        self,
        gemini_client: GeminiClientAdapter,
        httpx_mock: HTTPXMock,
        mock_tenacity_sleep: None,
    ) -> None:
        httpx_mock.add_response(
            url="https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
            method="POST",
            status_code=codes.TOO_MANY_REQUESTS,
            json={
                "error": {
                    "code": 429,
                    "status": "RESOURCE_EXHAUSTED",
                    "details": [
                        {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "3s"},
                    ],
                }
            },
            is_reusable=True,
        )

        with (
            pytest.raises(AdvisorRateLimitExceeded) as exc_info,
            mock.patch("asyncio.sleep", new_callable=mock.AsyncMock),
        ):
            await gemini_client.get_similar_tracks(artist_name="Radiohead", track_name="Creep")

        assert "Gemini rate limit exceeded after max retries for 'Creep' by 'Radiohead'" in str(exc_info.value)

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

    async def test__make_api_call__429__with_retry_delay__sleeps_and_retries(
        self,
        gemini_client: GeminiClientAdapter,
        httpx_mock: HTTPXMock,
        mock_tenacity_sleep: None,
    ) -> None:
        retry_delay: int = 3  # Within max_retry_wait=5 set in fixture
        expected_sleep: int = retry_delay + 1

        httpx_mock.add_response(
            url="https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
            method="POST",
            status_code=codes.TOO_MANY_REQUESTS,
            json={
                "error": {
                    "code": 429,
                    "message": "You exceeded your current quota.",
                    "status": "RESOURCE_EXHAUSTED",
                    "details": [
                        {"@type": "type.googleapis.com/google.rpc.Help", "links": []},
                        {"@type": "type.googleapis.com/google.rpc.QuotaFailure", "violations": []},
                        {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "3s"},
                    ],
                }
            },
        )
        httpx_mock.add_response(
            url="https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
            method="POST",
            status_code=codes.OK,
            json={"success": True},
        )

        with mock.patch("asyncio.sleep", new_callable=mock.AsyncMock) as mock_sleep:
            response = await gemini_client.make_api_call(
                method="POST",
                endpoint="/models/gemini-2.5-flash:generateContent",
            )

        mock_sleep.assert_any_call(expected_sleep)
        assert response == {"success": True}
        assert len(httpx_mock.get_requests()) == 2

    async def test__make_api_call__429__with_retry_delay__exceeds_max(
        self,
        gemini_client: GeminiClientAdapter,
        httpx_mock: HTTPXMock,
    ) -> None:
        assert gemini_client._max_retry_wait == 5
        retry_delay: int = 10

        httpx_mock.add_response(
            url="https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
            method="POST",
            status_code=codes.TOO_MANY_REQUESTS,
            json={
                "error": {
                    "code": 429,
                    "status": "RESOURCE_EXHAUSTED",
                    "details": [
                        {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": f"{retry_delay}s"},
                    ],
                }
            },
        )

        with pytest.raises(AdvisorRateLimitExceeded):
            await gemini_client.make_api_call(
                method="POST",
                endpoint="/models/gemini-2.5-flash:generateContent",
            )

        assert len(httpx_mock.get_requests()) == 1

    async def test__make_api_call__429__without_retry_delay__exponential_backoff(
        self,
        gemini_client: GeminiClientAdapter,
        httpx_mock: HTTPXMock,
        mock_tenacity_sleep: None,
    ) -> None:
        httpx_mock.add_response(
            url="https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
            method="POST",
            status_code=codes.TOO_MANY_REQUESTS,
            json={"error": {"code": 429, "details": []}},  # No RetryInfo
        )
        httpx_mock.add_response(
            url="https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
            method="POST",
            status_code=codes.OK,
            json={"success": True},
        )

        with mock.patch("asyncio.sleep", new_callable=mock.AsyncMock) as mock_sleep:
            response = await gemini_client.make_api_call(
                method="POST",
                endpoint="/models/gemini-2.5-flash:generateContent",
            )

        mock_sleep.assert_not_called()
        assert response == {"success": True}
        assert len(httpx_mock.get_requests()) == 2

    async def test__make_api_call__5xx__retries_and_raises(
        self,
        gemini_client: GeminiClientAdapter,
        httpx_mock: HTTPXMock,
        mock_tenacity_sleep: None,
    ) -> None:
        httpx_mock.add_response(
            url="https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
            method="POST",
            status_code=codes.INTERNAL_SERVER_ERROR,
            is_reusable=True,
        )

        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            await gemini_client.make_api_call(
                method="POST",
                endpoint="/models/gemini-2.5-flash:generateContent",
            )

        assert exc_info.value.response.status_code == codes.INTERNAL_SERVER_ERROR

    async def test__make_api_call__no_content__returns_empty(
        self,
        gemini_client: GeminiClientAdapter,
        httpx_mock: HTTPXMock,
    ) -> None:
        httpx_mock.add_response(
            url="https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
            method="POST",
            status_code=codes.NO_CONTENT,
        )

        response = await gemini_client.make_api_call(
            method="POST", endpoint="/models/gemini-2.5-flash:generateContent"
        )

        assert response == {}

    async def test__make_api_call__network_error__retries_and_raises(
        self,
        gemini_client: GeminiClientAdapter,
        httpx_mock: HTTPXMock,
        mock_tenacity_sleep: None,
    ) -> None:
        httpx_mock.add_exception(httpx.ConnectError("connection refused"), is_reusable=True)

        with pytest.raises(httpx.ConnectError):
            await gemini_client.make_api_call(method="POST", endpoint="/models/gemini-2.5-flash:generateContent")

    async def test__make_api_call__malformed_json_response__raises(
        self,
        gemini_client: GeminiClientAdapter,
        httpx_mock: HTTPXMock,
    ) -> None:
        httpx_mock.add_response(
            url="https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
            method="POST",
            status_code=codes.OK,
            content=b"not-valid-json",
        )

        with pytest.raises(ValueError):
            await gemini_client.make_api_call(method="POST", endpoint="/models/gemini-2.5-flash:generateContent")
