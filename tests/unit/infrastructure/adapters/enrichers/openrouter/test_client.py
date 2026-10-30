import json
from typing import Any

import pytest
from pytest_httpx import HTTPXMock

from museflow.domain.enums import EnrichField
from museflow.domain.enums import GenreTag
from museflow.infrastructure.adapters.enrichers.openrouter.client import OpenRouterTrackEnricherAdapter

from tests.unit.factories.entities.track import TrackFactory

URL = "https://openrouter.ai/api/v1/chat/completions"


@pytest.fixture
def completion(request: pytest.FixtureRequest) -> dict[str, Any]:
    return {
        "model": "google/gemini-2.5-flash-lite",
        "choices": [
            {
                "message": {"role": "assistant", "content": json.dumps({"enriched_tracks": request.param})},
                "finish_reason": "stop",
            }
        ],
    }


class TestOpenRouterTrackEnricherAdapter:
    async def test__enrich_tracks__no_choices__returns_empty(
        self,
        openrouter_enricher: OpenRouterTrackEnricherAdapter,
        httpx_mock: HTTPXMock,
    ) -> None:
        httpx_mock.add_response(url=URL, method="POST", json={"choices": []})

        result = await openrouter_enricher.enrich_tracks(TrackFactory.batch(1), fields=frozenset(EnrichField))

        assert result == []

    async def test__enrich_tracks__invalid_json__returns_empty(
        self,
        openrouter_enricher: OpenRouterTrackEnricherAdapter,
        httpx_mock: HTTPXMock,
    ) -> None:
        httpx_mock.add_response(
            url=URL,
            method="POST",
            json={"choices": [{"message": {"content": "not valid json {{{"}, "finish_reason": "stop"}]},
            is_reusable=True,
        )

        result = await openrouter_enricher.enrich_tracks(TrackFactory.batch(1), fields=frozenset(EnrichField))

        assert result == []
        assert len(httpx_mock.get_requests()) == 3  # initial call + 2 self-healing retries

    @pytest.mark.parametrize(
        "completion",
        [[{"track_index": 0, "genres": ["hip-hop", "NOT_A_GENRE", "afro rap"], "moods": ["chill", "NOT_A_MOOD"]}]],
        indirect=True,
    )
    async def test__enrich_tracks__unknown_tags__silently_dropped(
        self,
        openrouter_enricher: OpenRouterTrackEnricherAdapter,
        completion: dict[str, Any],
        httpx_mock: HTTPXMock,
    ) -> None:
        httpx_mock.add_response(url=URL, method="POST", json=completion)

        result = await openrouter_enricher.enrich_tracks([TrackFactory.build()], fields=frozenset(EnrichField))

        assert len(result) == 1
        assert result[0].genres == [GenreTag.HIP_HOP, GenreTag.AFRO_RAP]
        assert result[0].moods == ["chill"]

    @pytest.mark.parametrize(
        "completion",
        [[{"track_index": 0, "genres": ["hip-hop"]}, {"track_index": 5, "genres": ["rap"]}]],
        indirect=True,
    )
    async def test__enrich_tracks__out_of_range_index__dropped(
        self,
        openrouter_enricher: OpenRouterTrackEnricherAdapter,
        completion: dict[str, Any],
        httpx_mock: HTTPXMock,
    ) -> None:
        httpx_mock.add_response(url=URL, method="POST", json=completion)
        track = TrackFactory.build()

        result = await openrouter_enricher.enrich_tracks([track], fields=frozenset({EnrichField.GENRE}))

        assert [enrichment.track_id for enrichment in result] == [track.id]

    @pytest.mark.parametrize(
        ("completion", "expected"),
        [
            pytest.param(
                [{"track_index": 0, "locales": ["FR", "en", "fr"]}], ["fr", "en"], id="normalized_deduplicated"
            ),
            pytest.param([{"track_index": 0, "locales": ["fra"]}], None, id="only_invalid"),
            pytest.param([{"track_index": 0, "locales": None}], None, id="null"),
        ],
        indirect=["completion"],
    )
    async def test__enrich_tracks__locales(
        self,
        openrouter_enricher: OpenRouterTrackEnricherAdapter,
        completion: dict[str, Any],
        expected: list[str] | None,
        httpx_mock: HTTPXMock,
    ) -> None:
        httpx_mock.add_response(url=URL, method="POST", json=completion)

        result = await openrouter_enricher.enrich_tracks(
            [TrackFactory.build()], fields=frozenset({EnrichField.LOCALE})
        )

        assert len(result) == 1
        assert result[0].locales == expected

    @pytest.mark.parametrize("completion", [[{"track_index": 0, "locales": ["fr"]}]], indirect=True)
    async def test__enrich_tracks__locales_only__prompt_omits_genre_and_mood(
        self,
        openrouter_enricher: OpenRouterTrackEnricherAdapter,
        completion: dict[str, Any],
        httpx_mock: HTTPXMock,
    ) -> None:
        httpx_mock.add_response(url=URL, method="POST", json=completion)
        track = TrackFactory.build()

        result = await openrouter_enricher.enrich_tracks([track], fields=frozenset({EnrichField.LOCALE}))

        assert result[0].locales == ["fr"]
        assert result[0].genres == []
        assert result[0].moods == []
        body = json.loads(httpx_mock.get_requests()[0].content)
        system_message, user_message = body["messages"]
        assert system_message["role"] == "system"
        assert "GENRE" not in system_message["content"]
        assert "MOOD" not in system_message["content"]
        assert "LOCALE" in system_message["content"]
        assert json.loads(user_message["content"]) == [
            {"index": 0, "title": track.name, "primary_artist": track.primary_artist}
        ]
        assert body["model"] == "google/gemini-2.5-flash-lite"
        assert body["response_format"]["json_schema"]["name"] == "EnrichmentResponse"

    @pytest.mark.parametrize("completion", [[{"track_index": 0, "genres": ["hip-hop", "rap"]}]], indirect=True)
    async def test__enrich_tracks__genre_only__prompt_omits_locale_and_mood(
        self,
        openrouter_enricher: OpenRouterTrackEnricherAdapter,
        completion: dict[str, Any],
        httpx_mock: HTTPXMock,
    ) -> None:
        httpx_mock.add_response(url=URL, method="POST", json=completion)

        result = await openrouter_enricher.enrich_tracks([TrackFactory.build()], fields=frozenset({EnrichField.GENRE}))

        assert result[0].genres == [GenreTag.HIP_HOP, GenreTag.RAP]
        assert result[0].moods == []
        assert result[0].locales is None
        system_content = json.loads(httpx_mock.get_requests()[0].content)["messages"][0]["content"]
        assert "GENRE" in system_content
        assert "MOOD" not in system_content
        assert "LOCALE" not in system_content
