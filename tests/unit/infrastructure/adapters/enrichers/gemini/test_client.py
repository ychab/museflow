from pytest_httpx import HTTPXMock

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

        result = await gemini_enricher.enrich_tracks(TrackFactory.batch(1))

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

        result = await gemini_enricher.enrich_tracks(TrackFactory.batch(1))

        assert result == []
