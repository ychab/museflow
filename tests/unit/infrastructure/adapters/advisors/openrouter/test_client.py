import json
from typing import Any

from httpx import codes

import pytest
from pytest_httpx import HTTPXMock

from museflow.domain.entities.taste import TasteProfile
from museflow.domain.entities.track import Track
from museflow.domain.entities.user import User
from museflow.domain.enums import DiscoveryFocus
from museflow.domain.exceptions import AdvisorRateLimitExceededError
from museflow.domain.exceptions import DiscoveryTasteStrategyError
from museflow.infrastructure.adapters.advisors.openrouter.client import OpenRouterAdvisorAdapter

from tests.unit.factories.entities.taste import TasteProfileDataFactory
from tests.unit.factories.entities.taste import TasteProfileFactory
from tests.unit.factories.entities.track import TrackFactory
from tests.unit.factories.value_objects.discovery import ArtistSuggestedFactory
from tests.unit.factories.value_objects.discovery import DiscoveryArtistStrategyFactory

URL = "https://openrouter.ai/api/v1/chat/completions"


class TestOpenRouterAdvisorAdapter:
    @pytest.fixture
    def completion(self) -> dict[str, Any]:
        content = {
            "reasoning": "good fit",
            "strategy_label": "Horizon",
            "recommended_artists": [{"name": "Artist X", "sound": "Warm brass", "score": 0.9}],
            "suggested_playlist_name": "My Mix",
        }
        return {
            "model": "google/gemini-2.5-flash",
            "choices": [{"message": {"role": "assistant", "content": json.dumps(content)}, "finish_reason": "stop"}],
        }

    def test__display_name(self, openrouter_advisor: OpenRouterAdvisorAdapter) -> None:
        assert openrouter_advisor.display_name == "OpenRouter"

    async def test__get_discovery_artists__nominal(
        self,
        openrouter_advisor: OpenRouterAdvisorAdapter,
        taste_profile: TasteProfile,
        completion: dict[str, Any],
        httpx_mock: HTTPXMock,
    ) -> None:
        httpx_mock.add_response(url=URL, method="POST", json=completion)

        strategy = await openrouter_advisor.get_discovery_artists(
            profile=taste_profile,
            artists_limit=5,
            prompt="lo-fi jazz and soul for focus",
            focus=DiscoveryFocus.EXPANSION,
        )

        assert strategy.strategy_label == "Horizon"
        assert [artist.name for artist in strategy.artists] == ["Artist X"]
        body = json.loads(httpx_mock.get_requests()[0].content)
        assert body["model"] == "google/gemini-2.5-flash"
        assert body["response_format"]["json_schema"]["name"] == "DiscoveryArtistsResponse"
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
            pytest.param(None, None, "Recommend new artists for this user.", id="neither"),
        ],
    )
    async def test__get_discovery_artists__user_message(
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

        await openrouter_advisor.get_discovery_artists(
            profile=taste_profile,
            artists_limit=5,
            prompt=prompt,
            focus=focus,
        )

        system_message, user_message = json.loads(httpx_mock.get_requests()[0].content)["messages"]
        assert ("### FOCUS STRATEGY" in system_message["content"]) is (focus is not None)
        # Without a request, the profile leads alone: no rule on what a request settles.
        assert ("### USER REQUEST VS TASTE PROFILE" in system_message["content"]) is (prompt is not None)
        assert ("### ARTISTS NAMED IN THE REQUEST" in system_message["content"]) is (prompt is not None)
        assert user_message["content"] == expected_message

    async def test__get_discovery_artists__with_excluded_artists_builds_exclusion_block(
        self,
        openrouter_advisor: OpenRouterAdvisorAdapter,
        taste_profile: TasteProfile,
        completion: dict[str, Any],
        httpx_mock: HTTPXMock,
    ) -> None:
        httpx_mock.add_response(url=URL, method="POST", json=completion)

        await openrouter_advisor.get_discovery_artists(
            profile=taste_profile,
            focus=DiscoveryFocus.EXPANSION,
            artists_limit=5,
            excluded_artists=["Some Artist"],
        )

        system_message = json.loads(httpx_mock.get_requests()[0].content)["messages"][0]["content"]
        assert "### EXCLUSION LIST (DO NOT SUGGEST THESE)\n" in system_message
        assert "- Some Artist" in system_message

    async def test__get_discovery_artists__with_blacklisted_builds_sections(
        self,
        openrouter_advisor: OpenRouterAdvisorAdapter,
        taste_profile: TasteProfile,
        completion: dict[str, Any],
        httpx_mock: HTTPXMock,
    ) -> None:
        httpx_mock.add_response(url=URL, method="POST", json=completion)

        await openrouter_advisor.get_discovery_artists(
            profile=taste_profile,
            focus=DiscoveryFocus.EXPANSION,
            artists_limit=5,
            blacklisted_artists=["Taylor Swift"],
            blacklisted_tracks=["Shake It Off by Taylor Swift"],
        )

        body = httpx_mock.get_requests()[0].read().decode()
        assert "PERMANENTLY BLACKLISTED ARTISTS" in body
        assert "Taylor Swift" in body
        assert "PERMANENTLY BLACKLISTED TRACKS" in body
        assert "Shake It Off by Taylor Swift" in body

    async def test__get_discovery_artists__with_liked_tracks_builds_liked_block(
        self,
        openrouter_advisor: OpenRouterAdvisorAdapter,
        taste_profile: TasteProfile,
        completion: dict[str, Any],
        httpx_mock: HTTPXMock,
    ) -> None:
        httpx_mock.add_response(url=URL, method="POST", json=completion)
        liked: list[Track] = [TrackFactory.build(name="Hey Jude", artists=["The Beatles"])]

        await openrouter_advisor.get_discovery_artists(
            profile=taste_profile,
            focus=DiscoveryFocus.EXPANSION,
            artists_limit=5,
            liked_tracks=liked,
        )

        body = httpx_mock.get_requests()[0].read().decode()
        assert "LIKED TRACKS" in body
        assert "The Beatles" in body
        assert "Hey Jude" in body

    async def test__get_discovery_artists__with_disliked_tracks_builds_disliked_block(
        self,
        openrouter_advisor: OpenRouterAdvisorAdapter,
        taste_profile: TasteProfile,
        completion: dict[str, Any],
        httpx_mock: HTTPXMock,
    ) -> None:
        httpx_mock.add_response(url=URL, method="POST", json=completion)
        disliked: list[Track] = [TrackFactory.build(name="Plastic Anthem", artists=["The Fictional Band"])]

        await openrouter_advisor.get_discovery_artists(
            profile=taste_profile,
            artists_limit=5,
            disliked_tracks=disliked,
        )

        system_message = json.loads(httpx_mock.get_requests()[0].content)["messages"][0]["content"]
        assert "### DISLIKED TRACKS\n" in system_message
        assert "- The Fictional Band: Plastic Anthem" in system_message

    async def test__get_discovery_artists__with_covered_artists_builds_covered_artists_block(
        self,
        openrouter_advisor: OpenRouterAdvisorAdapter,
        taste_profile: TasteProfile,
        completion: dict[str, Any],
        httpx_mock: HTTPXMock,
    ) -> None:
        httpx_mock.add_response(url=URL, method="POST", json=completion)

        await openrouter_advisor.get_discovery_artists(
            profile=taste_profile,
            artists_limit=5,
            covered_artists={"The Fictional Band": 42},
        )

        system_message = json.loads(httpx_mock.get_requests()[0].content)["messages"][0]["content"]
        assert "### ARTISTS ALREADY COVERED IN THE LIBRARY\n" in system_message
        assert "- The Fictional Band (42 tracks)" in system_message

    @pytest.mark.parametrize(
        ("traits", "expected"),
        [
            pytest.param({"openness": 0.3, "adventurousness": 0.3}, "comfort zones", id="comfort_zone"),
            pytest.param({"openness": 0.8, "adventurousness": 0.5}, "adventurous", id="adventurous"),
        ],
    )
    async def test__get_discovery_artists__risk_calibration(
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

        await openrouter_advisor.get_discovery_artists(
            profile=profile, focus=DiscoveryFocus.EXPANSION, artists_limit=5
        )

        assert expected in httpx_mock.get_requests()[0].read().decode()

    async def test__get_discovery_artists__no_choices__raises(
        self,
        openrouter_advisor: OpenRouterAdvisorAdapter,
        taste_profile: TasteProfile,
        httpx_mock: HTTPXMock,
    ) -> None:
        httpx_mock.add_response(url=URL, method="POST", json={"choices": []})

        with pytest.raises(DiscoveryTasteStrategyError, match="Invalid discovery strategy response"):
            await openrouter_advisor.get_discovery_artists(
                profile=taste_profile,
                focus=DiscoveryFocus.EXPANSION,
                artists_limit=5,
            )

    async def test__get_discovery_artists__schema_violation__self_heals_then_raises(
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
            await openrouter_advisor.get_discovery_artists(
                profile=taste_profile,
                focus=DiscoveryFocus.EXPANSION,
                artists_limit=5,
            )

        assert len(httpx_mock.get_requests()) == 3  # initial call + 2 self-healing retries

    async def test__get_discovery_artists__rate_limit__raises(
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
            await openrouter_advisor.get_discovery_artists(
                profile=taste_profile,
                focus=DiscoveryFocus.EXPANSION,
                artists_limit=5,
            )

    async def test__get_discovery_artists__request_rejected__raises(
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
            await openrouter_advisor.get_discovery_artists(
                profile=taste_profile,
                focus=DiscoveryFocus.EXPANSION,
                artists_limit=5,
            )

    async def test__pick_discovery_tracks__candidates_listed_by_id(
        self,
        openrouter_advisor: OpenRouterAdvisorAdapter,
        httpx_mock: HTTPXMock,
    ) -> None:
        httpx_mock.add_response(
            url=URL,
            method="POST",
            json={
                "choices": [
                    {"message": {"content": '{"picks": [{"id": "2", "score": 0.9}]}'}, "finish_reason": "stop"}
                ]
            },
        )
        artist = ArtistSuggestedFactory.build()
        requested = ArtistSuggestedFactory.build(requested=True)
        strategy = DiscoveryArtistStrategyFactory.build(artists=[artist, requested])
        dated = TrackFactory.build(name="Neon Harbor", album_name="Night Drive", album_year=1999)
        undated = TrackFactory.build(name="Glass Rain", album_name=None, album_year=None)
        requested_track = TrackFactory.build(name="Paper Moon", album_name="Late Lights", album_year=2021)

        tracks_picked = await openrouter_advisor.pick_discovery_tracks(
            strategy=strategy,
            candidates={artist.name: [dated, undated], requested.name: [requested_track]},
            tracks_limit=5,
            max_tracks_per_artist=3,
        )

        assert [tp.track for tp in tracks_picked] == [undated]
        body = json.loads(httpx_mock.get_requests()[0].content)
        assert body["response_format"]["json_schema"]["name"] == "DiscoveryPicksResponse"
        system_message, user_message = body["messages"]
        assert f"#### {artist.name}\nWanted sound: {artist.sound}\n" in system_message["content"]
        assert "- 1 | Neon Harbor | Night Drive | 1999\n- 2 | Glass Rain | ? | ?" in system_message["content"]
        # The artist whose own tracks the request asks for is marked: no per-artist limit for them.
        assert f"#### {requested.name} (REQUESTED)\nWanted sound: {requested.sound}\n" in system_message["content"]
        assert "- 3 | Paper Moon | Late Lights | 2021" in system_message["content"]
        assert user_message["content"] == "Choose the tracks for this playlist."

    async def test__pick_discovery_tracks__favourite_artists(
        self,
        openrouter_advisor: OpenRouterAdvisorAdapter,
        httpx_mock: HTTPXMock,
    ) -> None:
        """Without a strategy, the artists are the user's favourites, shown with the tracks they rated high."""
        httpx_mock.add_response(
            url=URL,
            method="POST",
            json={
                "choices": [
                    {"message": {"content": '{"picks": [{"id": "1", "score": 0.9}]}'}, "finish_reason": "stop"}
                ]
            },
        )
        unknown = TrackFactory.build(name="Neon Harbor", album_name="Night Drive", album_year=1999)
        other = TrackFactory.build(name="Glass Rain", album_name="Late Lights", album_year=2021)
        liked = TrackFactory.batch(2, artists=["The Fictional Band"])

        tracks_picked = await openrouter_advisor.pick_discovery_tracks(
            strategy=None,
            candidates={"The Fictional Band": [unknown], "Another Band": [other]},
            tracks_limit=5,
            max_tracks_per_artist=3,
            focus=DiscoveryFocus.FAVOURITE_ARTISTS,
            liked_tracks={"The Fictional Band": liked},
        )

        assert [tp.track for tp in tracks_picked] == [unknown]
        system_message, user_message = json.loads(httpx_mock.get_requests()[0].content)["messages"]
        assert "### YOUR STRATEGY" not in system_message["content"]
        assert "Wanted sound" not in system_message["content"]
        assert "- Focus strategy: favourite_artists\n" in system_message["content"]
        assert "### FAVOURITE ARTISTS\n" in system_message["content"]
        assert (
            f"#### The Fictional Band\nLiked by the user: {liked[0].name}; {liked[1].name}\n"
            "- 1 | Neon Harbor | Night Drive | 1999"
        ) in system_message["content"]
        assert "#### Another Band\n- 2 | Glass Rain | Late Lights | 2021" in system_message["content"]
        assert user_message["content"] == "Apply the 'favourite_artists' focus strategy."
