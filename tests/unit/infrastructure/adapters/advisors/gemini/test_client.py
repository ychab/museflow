from collections.abc import Iterable
from unittest import mock

import httpx
from httpx import codes

import pytest
from pytest_httpx import HTTPXMock

from museflow.domain.entities.taste import TasteProfile
from museflow.domain.entities.track import Track
from museflow.domain.entities.track import TrackSuggested
from museflow.domain.entities.user import User
from museflow.domain.exceptions import AdvisorRateLimitExceeded
from museflow.domain.exceptions import DiscoveryTasteStrategyException
from museflow.domain.types import DiscoveryFocus
from museflow.infrastructure.adapters.advisors.gemini.client import GeminiAdvisorAdapter

from tests.unit.factories.entities.taste import TasteProfileDataFactory
from tests.unit.factories.entities.taste import TasteProfileFactory
from tests.unit.factories.entities.track import TrackFactory


class TestGeminiAdvisorAdapter:
    @pytest.fixture
    def mock_tenacity_sleep(self) -> Iterable[None]:
        retry_controller = GeminiAdvisorAdapter.make_api_call.retry  # type: ignore[attr-defined]
        original_sleep = retry_controller.sleep

        retry_controller.sleep = mock.AsyncMock(return_value=None)
        yield
        retry_controller.sleep = original_sleep

    async def test__get_discovery_strategy__nominal(
        self,
        gemini_advisor: GeminiAdvisorAdapter,
        taste_profile: TasteProfile,
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
                                    "text": '{"reasoning": "good fit", "strategy_label": "Horizon", "recommended_tracks": [{"name": "Song A", "artists": ["Artist X"], "score": 0.9}], "search_queries": ["post-rock"], "suggested_playlist_name": "My Mix"}'
                                }
                            ],
                            "role": "model",
                        }
                    }
                ]
            },
        )

        strategy = await gemini_advisor.get_discovery_strategy(
            profile=taste_profile,
            focus=DiscoveryFocus.EXPANSION,
            advisor_limit=5,
            genre="metal",
            mood="melancholic",
            custom_instructions="avoid pop",
        )

        assert strategy.strategy_label == "Horizon"
        assert len(strategy.recommended_tracks) == 1

    async def test__get_discovery_strategy__with_excluded_tracks_builds_exclusion_block(
        self,
        gemini_advisor: GeminiAdvisorAdapter,
        taste_profile: TasteProfile,
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
                                    "text": '{"reasoning": "ok", "strategy_label": "X", "recommended_tracks": [], "search_queries": [], "suggested_playlist_name": "Mix"}'
                                }
                            ],
                            "role": "model",
                        }
                    }
                ]
            },
        )

        await gemini_advisor.get_discovery_strategy(
            profile=taste_profile,
            focus=DiscoveryFocus.EXPANSION,
            advisor_limit=5,
            excluded_tracks=[TrackSuggested(name="Some Song", artists=["Some Artist"], score=0.9)],
        )

        request = httpx_mock.get_requests()[0]
        body = request.read().decode()
        assert "EXCLUSION LIST" in body
        assert "Some Artist" in body
        assert "Some Song" in body

    async def test__get_discovery_strategy__empty_candidates_raises(
        self,
        gemini_advisor: GeminiAdvisorAdapter,
        taste_profile: TasteProfile,
        httpx_mock: HTTPXMock,
    ) -> None:
        httpx_mock.add_response(
            url="https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
            method="POST",
            json={"candidates": []},
        )

        with pytest.raises(DiscoveryTasteStrategyException):
            await gemini_advisor.get_discovery_strategy(
                profile=taste_profile,
                focus=DiscoveryFocus.EXPANSION,
                advisor_limit=5,
            )

    async def test__get_discovery_strategy__invalid_json_raises(
        self,
        gemini_advisor: GeminiAdvisorAdapter,
        taste_profile: TasteProfile,
        httpx_mock: HTTPXMock,
    ) -> None:
        httpx_mock.add_response(
            url="https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
            method="POST",
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [{"text": '{"wrong_key": "oops"}'}],
                            "role": "model",
                        }
                    }
                ]
            },
        )

        with pytest.raises(DiscoveryTasteStrategyException):
            await gemini_advisor.get_discovery_strategy(
                profile=taste_profile,
                focus=DiscoveryFocus.EXPANSION,
                advisor_limit=5,
            )

    async def test__get_discovery_strategy__rate_limit_exhausted_raises(
        self,
        gemini_advisor: GeminiAdvisorAdapter,
        taste_profile: TasteProfile,
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
            await gemini_advisor.get_discovery_strategy(
                profile=taste_profile,
                focus=DiscoveryFocus.EXPANSION,
                advisor_limit=5,
            )

        assert "Gemini rate limit exceeded after max retries for discovery strategy" in str(exc_info.value)

    def test__display_name(self, gemini_advisor: GeminiAdvisorAdapter) -> None:
        assert gemini_advisor.display_name == "Gemini"

    async def test__make_api_call__429__with_retry_delay__sleeps_and_retries(
        self,
        gemini_advisor: GeminiAdvisorAdapter,
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
            response = await gemini_advisor.make_api_call(
                method="POST",
                endpoint="/models/gemini-2.5-flash:generateContent",
            )

        mock_sleep.assert_any_call(expected_sleep)
        assert response == {"success": True}
        assert len(httpx_mock.get_requests()) == 2

    async def test__make_api_call__429__with_retry_delay__exceeds_max(
        self,
        gemini_advisor: GeminiAdvisorAdapter,
        httpx_mock: HTTPXMock,
    ) -> None:
        assert gemini_advisor._max_retry_wait == 5
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
            await gemini_advisor.make_api_call(
                method="POST",
                endpoint="/models/gemini-2.5-flash:generateContent",
            )

        assert len(httpx_mock.get_requests()) == 1

    async def test__make_api_call__429__without_retry_delay__exponential_backoff(
        self,
        gemini_advisor: GeminiAdvisorAdapter,
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
            response = await gemini_advisor.make_api_call(
                method="POST",
                endpoint="/models/gemini-2.5-flash:generateContent",
            )

        mock_sleep.assert_not_called()
        assert response == {"success": True}
        assert len(httpx_mock.get_requests()) == 2

    async def test__make_api_call__5xx__retries_and_raises(
        self,
        gemini_advisor: GeminiAdvisorAdapter,
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
            await gemini_advisor.make_api_call(
                method="POST",
                endpoint="/models/gemini-2.5-flash:generateContent",
            )

        assert exc_info.value.response.status_code == codes.INTERNAL_SERVER_ERROR

    async def test__make_api_call__no_content__returns_empty(
        self,
        gemini_advisor: GeminiAdvisorAdapter,
        httpx_mock: HTTPXMock,
    ) -> None:
        httpx_mock.add_response(
            url="https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
            method="POST",
            status_code=codes.NO_CONTENT,
        )

        response = await gemini_advisor.make_api_call(
            method="POST", endpoint="/models/gemini-2.5-flash:generateContent"
        )

        assert response == {}

    async def test__make_api_call__network_error__retries_and_raises(
        self,
        gemini_advisor: GeminiAdvisorAdapter,
        httpx_mock: HTTPXMock,
        mock_tenacity_sleep: None,
    ) -> None:
        httpx_mock.add_exception(httpx.ConnectError("connection refused"), is_reusable=True)

        with pytest.raises(httpx.ConnectError):
            await gemini_advisor.make_api_call(method="POST", endpoint="/models/gemini-2.5-flash:generateContent")

    async def test__make_api_call__malformed_json_response__raises(
        self,
        gemini_advisor: GeminiAdvisorAdapter,
        httpx_mock: HTTPXMock,
    ) -> None:
        httpx_mock.add_response(
            url="https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
            method="POST",
            status_code=codes.OK,
            content=b"not-valid-json",
        )

        with pytest.raises(ValueError):
            await gemini_advisor.make_api_call(method="POST", endpoint="/models/gemini-2.5-flash:generateContent")

    async def test__get_discovery_strategy__with_blacklisted_builds_sections(
        self,
        gemini_advisor: GeminiAdvisorAdapter,
        taste_profile: TasteProfile,
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
                                    "text": '{"reasoning": "ok", "strategy_label": "X", "recommended_tracks": [], "search_queries": [], "suggested_playlist_name": "Mix"}'
                                }
                            ],
                            "role": "model",
                        }
                    }
                ]
            },
        )

        await gemini_advisor.get_discovery_strategy(
            profile=taste_profile,
            focus=DiscoveryFocus.EXPANSION,
            advisor_limit=5,
            blacklisted_artists=["Taylor Swift"],
            blacklisted_tracks=["Shake It Off by Taylor Swift"],
        )

        request = httpx_mock.get_requests()[0]
        body = request.read().decode()
        assert "PERMANENTLY BLACKLISTED ARTISTS" in body
        assert "Taylor Swift" in body
        assert "PERMANENTLY BLACKLISTED TRACKS" in body
        assert "Shake It Off by Taylor Swift" in body

    async def test__get_discovery_strategy__comfort_zone_risk_calibration(
        self,
        gemini_advisor: GeminiAdvisorAdapter,
        user: User,
        httpx_mock: HTTPXMock,
    ) -> None:
        profile = TasteProfileFactory.build(
            user_id=user.id,
            profile=TasteProfileDataFactory.build(behavioral_traits={"openness": 0.3, "adventurousness": 0.3}),
        )
        httpx_mock.add_response(
            url="https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
            method="POST",
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": '{"reasoning": "ok", "strategy_label": "X", "recommended_tracks": [], "search_queries": [], "suggested_playlist_name": "Mix"}'
                                }
                            ],
                            "role": "model",
                        }
                    }
                ]
            },
        )

        await gemini_advisor.get_discovery_strategy(
            profile=profile,
            focus=DiscoveryFocus.EXPANSION,
            advisor_limit=5,
        )

        body = httpx_mock.get_requests()[0].read().decode()
        assert "comfort zones" in body

    async def test__get_discovery_strategy__with_liked_tracks_builds_liked_block(
        self,
        gemini_advisor: GeminiAdvisorAdapter,
        taste_profile: TasteProfile,
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
                                    "text": '{"reasoning": "ok", "strategy_label": "X", "recommended_tracks": [], "search_queries": [], "suggested_playlist_name": "Mix"}'
                                }
                            ],
                            "role": "model",
                        }
                    }
                ]
            },
        )
        liked: list[Track] = [TrackFactory.build(name="Hey Jude", artists=["The Beatles"])]

        await gemini_advisor.get_discovery_strategy(
            profile=taste_profile,
            focus=DiscoveryFocus.EXPANSION,
            advisor_limit=5,
            liked_tracks=liked,
        )

        body = httpx_mock.get_requests()[0].read().decode()
        assert "LIKED TRACKS" in body
        assert "The Beatles" in body
        assert "Hey Jude" in body

    async def test__get_discovery_strategy__adventurous_risk_calibration(
        self,
        gemini_advisor: GeminiAdvisorAdapter,
        user: User,
        httpx_mock: HTTPXMock,
    ) -> None:
        profile = TasteProfileFactory.build(
            user_id=user.id,
            profile=TasteProfileDataFactory.build(behavioral_traits={"openness": 0.8, "adventurousness": 0.5}),
        )
        httpx_mock.add_response(
            url="https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
            method="POST",
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": '{"reasoning": "ok", "strategy_label": "X", "recommended_tracks": [], "search_queries": [], "suggested_playlist_name": "Mix"}'
                                }
                            ],
                            "role": "model",
                        }
                    }
                ]
            },
        )

        await gemini_advisor.get_discovery_strategy(
            profile=profile,
            focus=DiscoveryFocus.EXPANSION,
            advisor_limit=5,
        )

        body = httpx_mock.get_requests()[0].read().decode()
        assert "adventurous" in body
