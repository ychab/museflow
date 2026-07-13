import json

from pytest_httpx import HTTPXMock

from museflow.domain.enums import EnrichField
from museflow.domain.enums import GenreTag
from museflow.infrastructure.adapters.enrichers.gemini.client import GeminiTrackEnricherAdapter

from tests.unit.factories.entities.track import TrackFactory


class TestGeminiTrackEnricherAdapter:
    async def test__enrich_tracks__no_candidates__returns_empty(
        self,
        gemini_enricher: GeminiTrackEnricherAdapter,
        httpx_mock: HTTPXMock,
    ) -> None:
        httpx_mock.add_response(
            url="https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent",
            method="POST",
            json={"candidates": []},
        )

        result = await gemini_enricher.enrich_tracks(TrackFactory.batch(1), fields=frozenset(EnrichField))

        assert result == []

    async def test__enrich_tracks__invalid_json__returns_empty(
        self,
        gemini_enricher: GeminiTrackEnricherAdapter,
        httpx_mock: HTTPXMock,
    ) -> None:
        httpx_mock.add_response(
            url="https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent",
            method="POST",
            json={"candidates": [{"content": {"parts": [{"text": "not valid json {{{"}], "role": "model"}}]},
        )

        result = await gemini_enricher.enrich_tracks(TrackFactory.batch(1), fields=frozenset(EnrichField))

        assert result == []

    async def test__enrich_tracks__unknown_genre__silently_dropped(
        self,
        gemini_enricher: GeminiTrackEnricherAdapter,
        httpx_mock: HTTPXMock,
    ) -> None:
        track = TrackFactory.build()
        payload = json.dumps(
            {
                "enriched_tracks": [
                    {"track_index": 0, "genres": ["hip-hop", "NOT_A_GENRE", "afro rap"], "moods": ["chill"]}
                ]
            }
        )
        httpx_mock.add_response(
            url="https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent",
            method="POST",
            json={"candidates": [{"content": {"parts": [{"text": payload}], "role": "model"}}]},
        )

        result = await gemini_enricher.enrich_tracks([track], fields=frozenset(EnrichField))

        assert len(result) == 1
        assert result[0].genres == [GenreTag.HIP_HOP, GenreTag.AFRO_RAP]

    async def test__enrich_tracks__locale__valid__normalized(
        self,
        gemini_enricher: GeminiTrackEnricherAdapter,
        httpx_mock: HTTPXMock,
    ) -> None:
        track = TrackFactory.build()
        payload = json.dumps(
            {"enriched_tracks": [{"track_index": 0, "genres": ["hip-hop"], "moods": ["chill"], "locale": "FR"}]}
        )
        httpx_mock.add_response(
            url="https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent",
            method="POST",
            json={"candidates": [{"content": {"parts": [{"text": payload}], "role": "model"}}]},
        )

        result = await gemini_enricher.enrich_tracks([track], fields=frozenset(EnrichField))

        assert len(result) == 1
        assert result[0].locale == "fr"

    async def test__enrich_tracks__locale__invalid__silently_dropped(
        self,
        gemini_enricher: GeminiTrackEnricherAdapter,
        httpx_mock: HTTPXMock,
    ) -> None:
        track = TrackFactory.build()
        payload = json.dumps(
            {"enriched_tracks": [{"track_index": 0, "genres": ["hip-hop"], "moods": ["chill"], "locale": "fra"}]}
        )
        httpx_mock.add_response(
            url="https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent",
            method="POST",
            json={"candidates": [{"content": {"parts": [{"text": payload}], "role": "model"}}]},
        )

        result = await gemini_enricher.enrich_tracks([track], fields=frozenset(EnrichField))

        assert len(result) == 1
        assert result[0].locale is None

    async def test__enrich_tracks__locale__null__defaults_to_none(
        self,
        gemini_enricher: GeminiTrackEnricherAdapter,
        httpx_mock: HTTPXMock,
    ) -> None:
        track = TrackFactory.build()
        payload = json.dumps(
            {"enriched_tracks": [{"track_index": 0, "genres": ["hip-hop"], "moods": ["chill"], "locale": None}]}
        )
        httpx_mock.add_response(
            url="https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent",
            method="POST",
            json={"candidates": [{"content": {"parts": [{"text": payload}], "role": "model"}}]},
        )

        result = await gemini_enricher.enrich_tracks([track], fields=frozenset(EnrichField))

        assert len(result) == 1
        assert result[0].locale is None

    async def test__enrich_tracks__locale_only__prompt_omits_genre_taxonomy(
        self,
        gemini_enricher: GeminiTrackEnricherAdapter,
        httpx_mock: HTTPXMock,
    ) -> None:
        track = TrackFactory.build()
        payload = json.dumps({"enriched_tracks": [{"track_index": 0, "locale": "fr"}]})
        httpx_mock.add_response(
            url="https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent",
            method="POST",
            json={"candidates": [{"content": {"parts": [{"text": payload}], "role": "model"}}]},
        )

        result = await gemini_enricher.enrich_tracks([track], fields=frozenset({EnrichField.LOCALE}))

        assert len(result) == 1
        assert result[0].locale == "fr"
        assert result[0].genres == []
        assert result[0].moods == []

        request = httpx_mock.get_requests()[0]
        body = json.loads(request.content)
        system_text = body["system_instruction"]["parts"][0]["text"]
        assert "GENRE" not in system_text
        assert "MOOD" not in system_text
        assert "LOCALE" in system_text

    async def test__enrich_tracks__genre_only__prompt_omits_locale_and_mood(
        self,
        gemini_enricher: GeminiTrackEnricherAdapter,
        httpx_mock: HTTPXMock,
    ) -> None:
        track = TrackFactory.build()
        payload = json.dumps({"enriched_tracks": [{"track_index": 0, "genres": ["hip-hop", "rap"]}]})
        httpx_mock.add_response(
            url="https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent",
            method="POST",
            json={"candidates": [{"content": {"parts": [{"text": payload}], "role": "model"}}]},
        )

        result = await gemini_enricher.enrich_tracks([track], fields=frozenset({EnrichField.GENRE}))

        assert len(result) == 1
        assert result[0].genres == [GenreTag.HIP_HOP, GenreTag.RAP]
        assert result[0].moods == []
        assert result[0].locale is None

        request = httpx_mock.get_requests()[0]
        body = json.loads(request.content)
        system_text = body["system_instruction"]["parts"][0]["text"]
        assert "GENRE" in system_text
        assert "MOOD" not in system_text
        assert "LOCALE" not in system_text
