import logging

import pytest

from museflow.domain.entities.taste import TasteProfile
from museflow.domain.enums import DiscoveryFocus
from museflow.domain.value_objects.taste import DiscoveryArtistStrategy
from museflow.infrastructure.adapters.advisors.openrouter.client import OpenRouterAdvisorAdapter

from tests.integration.utils.wiremock import WireMockContext
from tests.unit.factories.entities.track import TrackFactory


@pytest.mark.wiremock("openrouter")
class TestOpenRouterAdvisorAdapter:
    async def test__get_discovery_strategy__nominal(
        self,
        openrouter_advisor: OpenRouterAdvisorAdapter,
        taste_profile: TasteProfile,
    ) -> None:
        strategy = await openrouter_advisor.get_discovery_strategy(
            profile=taste_profile,
            focus=DiscoveryFocus.EXPANSION,
            advisor_limit=5,
        )

        assert strategy.strategy_label == "Progressive Horizons"
        assert strategy.suggested_playlist_name == "Sonic Expansion - Progressive Horizons"
        assert len(strategy.recommended_tracks) == 1
        assert strategy.recommended_tracks[0].name == "Mi Pueblo"
        assert strategy.recommended_tracks[0].artists == ["Grupo Niche"]
        assert strategy.recommended_tracks[0].score == pytest.approx(1.0)

    async def test__get_discovery_strategy__invalid_response_then_valid__self_heals(
        self,
        openrouter_advisor: OpenRouterAdvisorAdapter,
        openrouter_wiremock: WireMockContext,
        taste_profile: TasteProfile,
    ) -> None:
        endpoint = "/chat/completions"
        invalid_body = {
            "choices": [{"message": {"role": "assistant", "content": '{"wrong_key": 1}'}, "finish_reason": "stop"}]
        }
        openrouter_wiremock.create_mapping(
            method="POST",
            url_path=endpoint,
            status=200,
            json_body=invalid_body,
            priority=0,
            scenario_name="advisor-self-healing",
            required_state="Started",
            new_state="invalid-served",
        )

        strategy = await openrouter_advisor.get_discovery_strategy(
            profile=taste_profile,
            focus=DiscoveryFocus.EXPANSION,
            advisor_limit=5,
        )

        assert strategy.strategy_label == "Progressive Horizons"
        assert len(strategy.recommended_tracks) == 1

    async def test__get_discovery_artists__nominal(
        self,
        openrouter_advisor: OpenRouterAdvisorAdapter,
        taste_profile: TasteProfile,
    ) -> None:
        strategy = await openrouter_advisor.get_discovery_artists(
            profile=taste_profile,
            artists_limit=5,
            focus=DiscoveryFocus.EXPANSION,
            excluded_artists=["An Earlier Band"],
        )

        assert strategy.strategy_label == "Progressive Horizons"
        assert strategy.suggested_playlist_name == "Sonic Expansion - Progressive Horizons"
        assert [artist.name for artist in strategy.artists] == ["Grupo Niche"]
        assert strategy.artists[0].score == pytest.approx(0.9)
        assert openrouter_advisor.usages[0].step == "advisor_artists"

    async def test__pick_discovery_tracks__nominal(
        self,
        openrouter_advisor: OpenRouterAdvisorAdapter,
        discovery_artist_strategy: DiscoveryArtistStrategy,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        first, second = TrackFactory.batch(2, album_name=None, album_year=None)
        artist = discovery_artist_strategy.artists[0].name

        with caplog.at_level(logging.WARNING):
            tracks_picked = await openrouter_advisor.pick_discovery_tracks(
                strategy=discovery_artist_strategy,
                candidates={artist: [first, second]},
                tracks_limit=5,
                max_tracks_per_artist=3,
                prompt="lo-fi jazz and soul for focus",
            )

        # The ids "1" and "2" are the candidates in order; the made-up id "99" is dropped.
        assert [(tp.track, tp.score) for tp in tracks_picked] == [(first, 0.9), (second, 0.8)]
        assert "Picks dropped, not among the candidates or picked twice: 1" in caplog.text
        assert openrouter_advisor.usages[0].step == "advisor_picks"

    async def test__pick_discovery_tracks__all_kept__no_warning(
        self,
        openrouter_advisor: OpenRouterAdvisorAdapter,
        openrouter_wiremock: WireMockContext,
        discovery_artist_strategy: DiscoveryArtistStrategy,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        openrouter_wiremock.create_mapping(
            method="POST",
            url_path="/chat/completions",
            status=200,
            json_body={
                "choices": [
                    {
                        "message": {"role": "assistant", "content": '{"picks": [{"id": "1", "score": 0.9}]}'},
                        "finish_reason": "stop",
                    }
                ]
            },
            priority=0,
        )
        track = TrackFactory.build()

        with caplog.at_level(logging.WARNING):
            tracks_picked = await openrouter_advisor.pick_discovery_tracks(
                strategy=discovery_artist_strategy,
                candidates={discovery_artist_strategy.artists[0].name: [track]},
                tracks_limit=5,
                max_tracks_per_artist=3,
            )

        assert [tp.track for tp in tracks_picked] == [track]
        assert "Picks dropped" not in caplog.text
