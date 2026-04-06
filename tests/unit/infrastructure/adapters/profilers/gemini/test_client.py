import json
from collections.abc import Iterable
from typing import Any
from unittest import mock

import httpx
from httpx import Request
from httpx import Response
from httpx import codes

import pytest
from pytest_httpx import HTTPXMock
from tenacity import TryAgain

from museflow.domain.entities.taste import TasteProfileData
from museflow.domain.exceptions import ProfilerRateLimitExceeded
from museflow.domain.exceptions import TasteProfileBuildException
from museflow.infrastructure.adapters.profilers.gemini.client import GeminiTasteProfileAdapter
from museflow.infrastructure.adapters.profilers.gemini.client import _is_retryable_error

from tests.integration.factories.models.taste import TasteProfileDataFactory
from tests.unit.factories.entities.music import TrackFactory


class TestGeminiTasteProfileAdapter:
    @pytest.fixture
    def mock_tenacity_sleep(self) -> Iterable[None]:
        retry_controller = GeminiTasteProfileAdapter.make_api_call.retry  # type: ignore[attr-defined]
        original_sleep = retry_controller.sleep

        retry_controller.sleep = mock.AsyncMock(return_value=None)
        yield
        retry_controller.sleep = original_sleep

    @pytest.fixture
    def profile_data(self, request: pytest.FixtureRequest) -> TasteProfileData:
        return TasteProfileDataFactory.build(
            **{
                "personality_archetype": None,
                "life_phase_insights": [],
                **getattr(request, "param", {}),
            },
        )

    @pytest.fixture
    def gemini_response(self, request: pytest.FixtureRequest, profile_data: TasteProfileData) -> dict[str, Any]:
        params = getattr(request, "param", {})
        profile = params.get("profile", profile_data)

        return {
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": json.dumps(profile)}],
                        "role": "model",
                    }
                }
            ]
        }

    def test__display_name(self, gemini_profiler: GeminiTasteProfileAdapter) -> None:
        assert gemini_profiler.display_name == "Gemini"

    def test__logic_version(self, gemini_profiler: GeminiTasteProfileAdapter) -> None:
        assert gemini_profiler.logic_version == "v1.0"

    async def test__retry_on_429__sleeps_and_retries(
        self,
        gemini_profiler: GeminiTasteProfileAdapter,
        gemini_response: dict[str, Any],
        httpx_mock: HTTPXMock,
        mock_tenacity_sleep: None,
    ) -> None:
        retry_delay = 3  # Within max_retry_wait=5 set in fixture
        httpx_mock.add_response(
            url=f"{gemini_profiler.base_url}models/gemini-2.5-flash:generateContent",
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
        httpx_mock.add_response(
            url=f"{gemini_profiler.base_url}models/gemini-2.5-flash:generateContent",
            method="POST",
            json=gemini_response,
        )

        with mock.patch("asyncio.sleep", new_callable=mock.AsyncMock) as mock_sleep:
            profile = await gemini_profiler.build_profile_segment(TrackFactory.batch(2))

        mock_sleep.assert_any_call(retry_delay + 1)
        assert profile

    async def test__retry_on_429__exceeds_max(
        self,
        gemini_profiler: GeminiTasteProfileAdapter,
        httpx_mock: HTTPXMock,
    ) -> None:
        assert gemini_profiler._max_retry_wait == 5
        retry_delay = 6  # Exceeds max_retry_wait=5

        httpx_mock.add_response(
            url=f"{gemini_profiler.base_url}models/gemini-2.5-flash:generateContent",
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

        with pytest.raises(ProfilerRateLimitExceeded):
            await gemini_profiler.build_profile_segment(TrackFactory.batch(2))

    async def test__invalid_response__raises_taste_profile_build_exception(
        self,
        gemini_profiler: GeminiTasteProfileAdapter,
        httpx_mock: HTTPXMock,
    ) -> None:
        httpx_mock.add_response(
            url=f"{gemini_profiler.base_url}models/gemini-2.5-flash:generateContent",
            method="POST",
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [{"text": '{"wrong_key": "bad"}'}],
                            "role": "model",
                        }
                    }
                ]
            },
        )

        with pytest.raises(TasteProfileBuildException):
            await gemini_profiler.build_profile_segment(TrackFactory.batch(2))

    async def test__build_profile_segment__no_dates(
        self,
        gemini_profiler: GeminiTasteProfileAdapter,
        gemini_response: dict[str, Any],
        httpx_mock: HTTPXMock,
    ) -> None:
        httpx_mock.add_response(
            url=f"{gemini_profiler.base_url}models/gemini-2.5-flash:generateContent",
            method="POST",
            json=gemini_response,
        )

        tracks = TrackFactory.batch(2, added_at=None, played_at=None)
        await gemini_profiler.build_profile_segment(tracks)

        request = httpx_mock.get_requests()[0]
        assert "[unknown period]" in request.content.decode()

    async def test__make_api_call__no_content(
        self,
        gemini_profiler: GeminiTasteProfileAdapter,
        httpx_mock: HTTPXMock,
    ) -> None:
        httpx_mock.add_response(
            url=f"{gemini_profiler.base_url}models/gemini-2.5-flash:generateContent",
            method="POST",
            status_code=codes.NO_CONTENT,
        )

        result = await gemini_profiler.make_api_call("POST", "/models/gemini-2.5-flash:generateContent")

        assert result == {}

    async def test__make_api_call__non_retryable_4xx(
        self,
        gemini_profiler: GeminiTasteProfileAdapter,
        httpx_mock: HTTPXMock,
    ) -> None:
        httpx_mock.add_response(
            url=f"{gemini_profiler.base_url}models/gemini-2.5-flash:generateContent",
            method="POST",
            status_code=403,
        )

        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            await gemini_profiler.make_api_call(
                "POST",
                "/models/gemini-2.5-flash:generateContent",
                headers={"x-goog-api-key": "dummy"},
            )

        assert exc_info.value.response.status_code == 403

    async def test__make_api_call__429_without_retry_delay(
        self,
        gemini_profiler: GeminiTasteProfileAdapter,
        httpx_mock: HTTPXMock,
        mock_tenacity_sleep: None,
    ) -> None:
        """429 response with no retryDelay in body falls through to logger.exception and re-raises."""
        # 429 with empty details → _parse_retry_delay returns None → falls to logger.exception
        # Tenacity sees 429 as retryable, so we need HTTP_MAX_RETRIES responses
        for _ in range(5):
            httpx_mock.add_response(
                url=f"{gemini_profiler.base_url}models/gemini-2.5-flash:generateContent",
                method="POST",
                status_code=codes.TOO_MANY_REQUESTS,
                json={"error": {"code": 429, "status": "RESOURCE_EXHAUSTED", "details": []}},
            )

        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            await gemini_profiler.make_api_call(
                "POST",
                "/models/gemini-2.5-flash:generateContent",
                headers={"x-goog-api-key": "dummy"},
            )

        assert exc_info.value.response.status_code == codes.TOO_MANY_REQUESTS

    async def test__call_gemini__try_again_exhausted(
        self,
        gemini_profiler: GeminiTasteProfileAdapter,
        httpx_mock: HTTPXMock,
        mock_tenacity_sleep: None,
    ) -> None:
        """When make_api_call raises TryAgain after max retries, _call_gemini converts it."""
        # Force TryAgain to propagate: 429 without retryDelay in body means TryAgain is raised
        # but tenacity will eventually exhaust retries and re-raise TryAgain
        # We mock make_api_call directly to return TryAgain after exhaustion
        with mock.patch.object(
            gemini_profiler,
            "make_api_call",
            new_callable=mock.AsyncMock,
            side_effect=TryAgain(),
        ):
            with pytest.raises(ProfilerRateLimitExceeded):
                await gemini_profiler.build_profile_segment(TrackFactory.batch(2))


class TestIsRetryableError:
    def test__http_status_error_500__returns_true(self) -> None:
        request = Request("POST", "https://example.com")
        response = Response(status_code=500, request=request)
        exc = httpx.HTTPStatusError("500", request=request, response=response)
        assert _is_retryable_error(exc) is True

    def test__request_error__returns_true(self) -> None:
        request = Request("POST", "https://example.com")
        exc = httpx.ConnectError("connection error", request=request)
        assert _is_retryable_error(exc) is True

    def test__try_again__returns_true(self) -> None:
        assert _is_retryable_error(TryAgain()) is True

    def test__other_exception__returns_false(self) -> None:
        assert _is_retryable_error(ValueError("something")) is False
