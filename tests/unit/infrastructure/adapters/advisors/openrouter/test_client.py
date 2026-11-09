import json
from typing import Any

from httpx import codes

import pytest
from pytest_httpx import HTTPXMock

from museflow.domain.entities.taste import TasteProfile
from museflow.domain.entities.track import Track
from museflow.domain.entities.track import TrackSuggested
from museflow.domain.entities.user import User
from museflow.domain.enums import DiscoveryFocus
from museflow.domain.exceptions import AdvisorRateLimitExceededError
from museflow.domain.exceptions import DiscoveryTasteStrategyError
from museflow.infrastructure.adapters.advisors.openrouter.client import OpenRouterAdvisorAdapter

from tests.unit.factories.entities.taste import TasteProfileDataFactory
from tests.unit.factories.entities.taste import TasteProfileFactory
from tests.unit.factories.entities.track import TrackFactory

URL = "https://openrouter.ai/api/v1/chat/completions"


class TestOpenRouterAdvisorAdapter:
    @pytest.fixture
    def completion(self) -> dict[str, Any]:
        content = {
            "reasoning": "good fit",
            "strategy_label": "Horizon",
            "recommended_tracks": [{"name": "Song A", "artists": ["Artist X"], "score": 0.9}],
            "suggested_playlist_name": "My Mix",
        }
        return {
            "model": "google/gemini-2.5-flash",
            "choices": [{"message": {"role": "assistant", "content": json.dumps(content)}, "finish_reason": "stop"}],
        }

    def test__display_name(self, openrouter_advisor: OpenRouterAdvisorAdapter) -> None:
        assert openrouter_advisor.display_name == "OpenRouter"

    async def test__get_discovery_strategy__nominal(
        self,
        openrouter_advisor: OpenRouterAdvisorAdapter,
        taste_profile: TasteProfile,
        completion: dict[str, Any],
        httpx_mock: HTTPXMock,
    ) -> None:
        httpx_mock.add_response(url=URL, method="POST", json=completion)

        strategy = await openrouter_advisor.get_discovery_strategy(
            profile=taste_profile,
            advisor_limit=5,
            prompt="lo-fi jazz and soul for focus",
            focus=DiscoveryFocus.EXPANSION,
        )

        assert strategy.strategy_label == "Horizon"
        assert [track.name for track in strategy.recommended_tracks] == ["Song A"]
        body = json.loads(httpx_mock.get_requests()[0].content)
        assert body["model"] == "google/gemini-2.5-flash"
        assert body["response_format"]["json_schema"]["name"] == "DiscoveryStrategyResponse"
        system_message, user_message = body["messages"]
        assert system_message["role"] == "system"
        assert "MuseFlow Navigator" in system_message["content"]
        assert "### FOCUS STRATEGY: expansion" in system_message["content"]
        assert user_message == {
            "role": "user",
            "content": "Apply the 'expansion' focus strategy. User request: lo-fi jazz and soul for focus",
        }

    @pytest.mark.parametrize(
        ("prompt", "focus", "expected_message"),
        [
            pytest.param("lo-fi jazz", None, "User request: lo-fi jazz", id="prompt_only"),
            pytest.param(
                None,
                DiscoveryFocus.ROOTS_REVIVAL,
                "Apply the 'roots_revival' focus strategy.",
                id="focus_only",
            ),
            pytest.param(None, None, "Recommend new tracks for this user.", id="neither"),
        ],
    )
    async def test__get_discovery_strategy__user_message(
        self,
        openrouter_advisor: OpenRouterAdvisorAdapter,
        taste_profile: TasteProfile,
        completion: dict[str, Any],
        httpx_mock: HTTPXMock,
        prompt: str | None,
        focus: DiscoveryFocus | None,
        expected_message: str,
    ) -> None:
        httpx_mock.add_response(url=URL, method="POST", json=completion)

        await openrouter_advisor.get_discovery_strategy(
            profile=taste_profile,
            advisor_limit=5,
            prompt=prompt,
            focus=focus,
        )

        system_message, user_message = json.loads(httpx_mock.get_requests()[0].content)["messages"]
        assert ("### FOCUS STRATEGY" in system_message["content"]) is (focus is not None)
        assert user_message["content"] == expected_message

    async def test__get_discovery_strategy__with_excluded_tracks_builds_exclusion_block(
        self,
        openrouter_advisor: OpenRouterAdvisorAdapter,
        taste_profile: TasteProfile,
        completion: dict[str, Any],
        httpx_mock: HTTPXMock,
    ) -> None:
        httpx_mock.add_response(url=URL, method="POST", json=completion)

        await openrouter_advisor.get_discovery_strategy(
            profile=taste_profile,
            focus=DiscoveryFocus.EXPANSION,
            advisor_limit=5,
            excluded_tracks=[TrackSuggested(name="Some Song", artists=["Some Artist"], score=0.9)],
        )

        body = httpx_mock.get_requests()[0].read().decode()
        assert "EXCLUSION LIST" in body
        assert "Some Artist" in body
        assert "Some Song" in body

    async def test__get_discovery_strategy__with_blacklisted_builds_sections(
        self,
        openrouter_advisor: OpenRouterAdvisorAdapter,
        taste_profile: TasteProfile,
        completion: dict[str, Any],
        httpx_mock: HTTPXMock,
    ) -> None:
        httpx_mock.add_response(url=URL, method="POST", json=completion)

        await openrouter_advisor.get_discovery_strategy(
            profile=taste_profile,
            focus=DiscoveryFocus.EXPANSION,
            advisor_limit=5,
            blacklisted_artists=["Taylor Swift"],
            blacklisted_tracks=["Shake It Off by Taylor Swift"],
        )

        body = httpx_mock.get_requests()[0].read().decode()
        assert "PERMANENTLY BLACKLISTED ARTISTS" in body
        assert "Taylor Swift" in body
        assert "PERMANENTLY BLACKLISTED TRACKS" in body
        assert "Shake It Off by Taylor Swift" in body

    async def test__get_discovery_strategy__with_liked_tracks_builds_liked_block(
        self,
        openrouter_advisor: OpenRouterAdvisorAdapter,
        taste_profile: TasteProfile,
        completion: dict[str, Any],
        httpx_mock: HTTPXMock,
    ) -> None:
        httpx_mock.add_response(url=URL, method="POST", json=completion)
        liked: list[Track] = [TrackFactory.build(name="Hey Jude", artists=["The Beatles"])]

        await openrouter_advisor.get_discovery_strategy(
            profile=taste_profile,
            focus=DiscoveryFocus.EXPANSION,
            advisor_limit=5,
            liked_tracks=liked,
        )

        body = httpx_mock.get_requests()[0].read().decode()
        assert "LIKED TRACKS" in body
        assert "The Beatles" in body
        assert "Hey Jude" in body

    async def test__get_discovery_strategy__with_disliked_tracks_builds_disliked_block(
        self,
        openrouter_advisor: OpenRouterAdvisorAdapter,
        taste_profile: TasteProfile,
        completion: dict[str, Any],
        httpx_mock: HTTPXMock,
    ) -> None:
        httpx_mock.add_response(url=URL, method="POST", json=completion)
        disliked: list[Track] = [TrackFactory.build(name="Plastic Anthem", artists=["The Fictional Band"])]

        await openrouter_advisor.get_discovery_strategy(
            profile=taste_profile,
            advisor_limit=5,
            disliked_tracks=disliked,
        )

        system_message = json.loads(httpx_mock.get_requests()[0].content)["messages"][0]["content"]
        assert "### DISLIKED TRACKS\n" in system_message
        assert "- The Fictional Band: Plastic Anthem" in system_message

    async def test__get_discovery_strategy__with_known_tracks_builds_known_block(
        self,
        openrouter_advisor: OpenRouterAdvisorAdapter,
        taste_profile: TasteProfile,
        completion: dict[str, Any],
        httpx_mock: HTTPXMock,
    ) -> None:
        httpx_mock.add_response(url=URL, method="POST", json=completion)

        await openrouter_advisor.get_discovery_strategy(
            profile=taste_profile,
            advisor_limit=5,
            excluded_tracks=[TrackSuggested(name="Unreconciled Song", artists=["Some Artist"], score=0.9)],
            known_tracks=[TrackSuggested(name="Known Song", artists=["Known Artist"], score=0.9)],
        )

        system_message = json.loads(httpx_mock.get_requests()[0].content)["messages"][0]["content"]
        exclusion_list, known_list = system_message.split("### ALREADY KNOWN BY THE USER")
        assert "- Some Artist: Unreconciled Song" in exclusion_list
        assert "Dig deeper" in known_list
        assert "- Known Artist: Known Song" in known_list

    async def test__get_discovery_strategy__with_top_listening_builds_top_blocks(
        self,
        openrouter_advisor: OpenRouterAdvisorAdapter,
        taste_profile: TasteProfile,
        completion: dict[str, Any],
        httpx_mock: HTTPXMock,
    ) -> None:
        httpx_mock.add_response(url=URL, method="POST", json=completion)

        await openrouter_advisor.get_discovery_strategy(
            profile=taste_profile,
            advisor_limit=5,
            top_played_tracks=[TrackFactory.build(name="Daily Loop", artists=["The Fictional Band"])],
            top_artists={"The Fictional Band": 42},
        )

        system_message = json.loads(httpx_mock.get_requests()[0].content)["messages"][0]["content"]
        top_tracks, top_artists = system_message.split("### TOP ARTISTS IN THE LIBRARY")
        assert "### TOP PLAYED TRACKS (DO NOT SUGGEST THESE)\n" in top_tracks
        assert "- The Fictional Band: Daily Loop" in top_tracks
        assert "- The Fictional Band (42 tracks)" in top_artists

    @pytest.mark.parametrize(
        ("traits", "expected"),
        [
            pytest.param({"openness": 0.3, "adventurousness": 0.3}, "comfort zones", id="comfort_zone"),
            pytest.param({"openness": 0.8, "adventurousness": 0.5}, "adventurous", id="adventurous"),
        ],
    )
    async def test__get_discovery_strategy__risk_calibration(
        self,
        openrouter_advisor: OpenRouterAdvisorAdapter,
        user: User,
        traits: dict[str, float],
        expected: str,
        completion: dict[str, Any],
        httpx_mock: HTTPXMock,
    ) -> None:
        profile = TasteProfileFactory.build(
            user_id=user.id,
            profile=TasteProfileDataFactory.build(behavioral_traits=traits),
        )
        httpx_mock.add_response(url=URL, method="POST", json=completion)

        await openrouter_advisor.get_discovery_strategy(
            profile=profile, focus=DiscoveryFocus.EXPANSION, advisor_limit=5
        )

        assert expected in httpx_mock.get_requests()[0].read().decode()

    async def test__get_discovery_strategy__no_choices__raises(
        self,
        openrouter_advisor: OpenRouterAdvisorAdapter,
        taste_profile: TasteProfile,
        httpx_mock: HTTPXMock,
    ) -> None:
        httpx_mock.add_response(url=URL, method="POST", json={"choices": []})

        with pytest.raises(DiscoveryTasteStrategyError, match="Invalid discovery strategy response"):
            await openrouter_advisor.get_discovery_strategy(
                profile=taste_profile,
                focus=DiscoveryFocus.EXPANSION,
                advisor_limit=5,
            )

    async def test__get_discovery_strategy__schema_violation__self_heals_then_raises(
        self,
        openrouter_advisor: OpenRouterAdvisorAdapter,
        taste_profile: TasteProfile,
        httpx_mock: HTTPXMock,
    ) -> None:
        httpx_mock.add_response(
            url=URL,
            method="POST",
            json={"choices": [{"message": {"content": '{"wrong_key": "oops"}'}, "finish_reason": "stop"}]},
            is_reusable=True,
        )

        with pytest.raises(DiscoveryTasteStrategyError):
            await openrouter_advisor.get_discovery_strategy(
                profile=taste_profile,
                focus=DiscoveryFocus.EXPANSION,
                advisor_limit=5,
            )

        assert len(httpx_mock.get_requests()) == 3  # initial call + 2 self-healing retries

    async def test__get_discovery_strategy__rate_limit__raises(
        self,
        openrouter_advisor: OpenRouterAdvisorAdapter,
        taste_profile: TasteProfile,
        httpx_mock: HTTPXMock,
    ) -> None:
        httpx_mock.add_response(
            url=URL,
            method="POST",
            status_code=codes.TOO_MANY_REQUESTS,
            headers={"Retry-After": "6"},  # above max_retry_wait=5
        )

        with pytest.raises(AdvisorRateLimitExceededError, match="exceeds max wait"):
            await openrouter_advisor.get_discovery_strategy(
                profile=taste_profile,
                focus=DiscoveryFocus.EXPANSION,
                advisor_limit=5,
            )

    async def test__get_discovery_strategy__request_rejected__raises(
        self,
        openrouter_advisor: OpenRouterAdvisorAdapter,
        taste_profile: TasteProfile,
        httpx_mock: HTTPXMock,
    ) -> None:
        httpx_mock.add_response(
            url=URL,
            method="POST",
            status_code=codes.PAYMENT_REQUIRED,
            json={"error": {"code": 402, "message": "Insufficient credits"}},
        )

        with pytest.raises(DiscoveryTasteStrategyError, match="Insufficient credits"):
            await openrouter_advisor.get_discovery_strategy(
                profile=taste_profile,
                focus=DiscoveryFocus.EXPANSION,
                advisor_limit=5,
            )
