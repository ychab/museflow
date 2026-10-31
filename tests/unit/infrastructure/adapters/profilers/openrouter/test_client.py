import json
from typing import Any

from httpx import codes

import pytest
from pytest_httpx import HTTPXMock

from museflow.domain.entities.taste import TasteProfileData
from museflow.domain.exceptions import TasteProfileBuildException
from museflow.domain.exceptions import TasteProfilerRateLimitExceeded
from museflow.infrastructure.adapters.profilers.openrouter.client import OpenRouterTasteProfileAdapter
from museflow.infrastructure.adapters.profilers.openrouter.client import _format_tracks

from tests.integration.factories.models.taste import TasteProfileDataFactory
from tests.unit.factories.entities.track import TrackFactory

URL = "https://openrouter.ai/api/v1/chat/completions"


class TestOpenRouterTasteProfileAdapter:
    @pytest.fixture
    def profile_data(self) -> TasteProfileData:
        return TasteProfileDataFactory.build(
            personality_archetype=None,
            life_phase_insights=[],
            core_identity={"indie-rock": 0.8, "melancholic": 0.4},  # valid tags, kept by the adapter filter
            current_vibe={"hip-hop": 0.6},
        )

    @pytest.fixture
    def completion(self, profile_data: TasteProfileData) -> dict[str, Any]:
        content = {
            **profile_data,
            "core_identity": [{"key": k, "value": v} for k, v in profile_data["core_identity"].items()],
            "current_vibe": [{"key": k, "value": v} for k, v in profile_data["current_vibe"].items()],
            "behavioral_traits": None,
        }
        return {
            "model": "google/gemini-2.5-flash-lite",
            "choices": [{"message": {"role": "assistant", "content": json.dumps(content)}, "finish_reason": "stop"}],
        }

    def test__display_name(self, openrouter_profiler: OpenRouterTasteProfileAdapter) -> None:
        assert openrouter_profiler.display_name == "OpenRouter"

    def test__logic_version(self, openrouter_profiler: OpenRouterTasteProfileAdapter) -> None:
        assert openrouter_profiler.logic_version == "v2.0"

    def test__profiler_metadata(self, openrouter_profiler: OpenRouterTasteProfileAdapter) -> None:
        metadata = openrouter_profiler.profiler_metadata

        assert metadata["gateway"] == "openrouter"
        assert metadata["steps"]["segment"] == {
            "model": "google/gemini-2.5-flash-lite",
            "fallback_models": [],
            "reasoning_effort": None,
            "max_tokens": None,
            "temperature": None,
        }
        assert metadata["steps"]["merge"]["model"] == "google/gemini-2.5-flash"
        assert metadata["steps"]["reflect"]["model"] == "google/gemini-2.5-pro"
        assert metadata["steps"]["reflect"]["reasoning_effort"] == "high"
        json.dumps(metadata)  # stored as JSONB

    async def test__build_profile_segment__null_traits(
        self,
        openrouter_profiler: OpenRouterTasteProfileAdapter,
        completion: dict[str, Any],
        profile_data: TasteProfileData,
        httpx_mock: HTTPXMock,
    ) -> None:
        httpx_mock.add_response(url=URL, method="POST", json=completion)

        profile = await openrouter_profiler.build_profile_segment(TrackFactory.batch(2))

        assert profile["behavioral_traits"] == {}
        assert profile["core_identity"] == profile_data["core_identity"]
        body = json.loads(httpx_mock.get_requests()[0].content)
        assert body["model"] == "google/gemini-2.5-flash-lite"
        assert body["response_format"]["json_schema"]["name"] == "TasteProfileResponse"
        assert [message["role"] for message in body["messages"]] == ["user"]

    async def test__build_profile_segment__no_dates(
        self,
        openrouter_profiler: OpenRouterTasteProfileAdapter,
        completion: dict[str, Any],
        httpx_mock: HTTPXMock,
    ) -> None:
        httpx_mock.add_response(url=URL, method="POST", json=completion)

        await openrouter_profiler.build_profile_segment(TrackFactory.batch(2, played_at_last=None))

        assert "[unknown period]" in httpx_mock.get_requests()[0].content.decode()

    async def test__merge_profiles__merge_model(
        self,
        openrouter_profiler: OpenRouterTasteProfileAdapter,
        completion: dict[str, Any],
        profile_data: TasteProfileData,
        httpx_mock: HTTPXMock,
    ) -> None:
        httpx_mock.add_response(url=URL, method="POST", json=completion)

        await openrouter_profiler.merge_profiles(profile_data, profile_data)

        body = json.loads(httpx_mock.get_requests()[0].content)
        assert body["model"] == "google/gemini-2.5-flash"
        assert "reasoning" not in body

    async def test__reflect_on_profile__reflect_model(
        self,
        openrouter_profiler: OpenRouterTasteProfileAdapter,
        completion: dict[str, Any],
        profile_data: TasteProfileData,
        httpx_mock: HTTPXMock,
    ) -> None:
        httpx_mock.add_response(url=URL, method="POST", json=completion)

        await openrouter_profiler.reflect_on_profile(profile_data)

        body = json.loads(httpx_mock.get_requests()[0].content)
        assert body["model"] == "google/gemini-2.5-pro"
        assert body["reasoning"] == {"effort": "high"}

    async def test__rate_limit__raises_rate_limit_exceeded(
        self,
        openrouter_profiler: OpenRouterTasteProfileAdapter,
        httpx_mock: HTTPXMock,
    ) -> None:
        httpx_mock.add_response(
            url=URL,
            method="POST",
            status_code=codes.TOO_MANY_REQUESTS,
            headers={"Retry-After": "6"},  # above max_retry_wait=5
        )

        with pytest.raises(TasteProfilerRateLimitExceeded, match="exceeds max wait"):
            await openrouter_profiler.build_profile_segment(TrackFactory.batch(2))

    async def test__request_rejected__raises_build_exception(
        self,
        openrouter_profiler: OpenRouterTasteProfileAdapter,
        httpx_mock: HTTPXMock,
    ) -> None:
        httpx_mock.add_response(
            url=URL,
            method="POST",
            status_code=codes.PAYMENT_REQUIRED,
            json={"error": {"code": 402, "message": "Insufficient credits"}},
        )

        with pytest.raises(TasteProfileBuildException, match="Insufficient credits"):
            await openrouter_profiler.build_profile_segment(TrackFactory.batch(2))

    async def test__invalid_response__raises_build_exception(
        self,
        openrouter_profiler: OpenRouterTasteProfileAdapter,
        httpx_mock: HTTPXMock,
    ) -> None:
        httpx_mock.add_response(
            url=URL,
            method="POST",
            json={"choices": [{"message": {"content": '{"wrong_key": "bad"}'}, "finish_reason": "stop"}]},
            is_reusable=True,
        )

        with pytest.raises(TasteProfileBuildException, match="Invalid taste profile response"):
            await openrouter_profiler.build_profile_segment(TrackFactory.batch(2))

        assert len(httpx_mock.get_requests()) == 3  # initial call + 2 self-healing retries


class TestFormatTracks:
    def test__unrated_track__no_score_field(self) -> None:
        track = TrackFactory.build(score=None)
        assert "score:" not in _format_tracks([track])

    def test__score_zero__shown(self) -> None:
        track = TrackFactory.build(score=0)
        assert "score:0" in _format_tracks([track])

    def test__scored_track__shown(self) -> None:
        track = TrackFactory.build(score=8)
        assert "score:8" in _format_tracks([track])
