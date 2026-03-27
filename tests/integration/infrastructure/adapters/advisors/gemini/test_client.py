import pytest

from museflow.infrastructure.adapters.advisors.gemini.client import GeminiClientAdapter


@pytest.mark.wiremock("gemini")
class TestGeminiClientAdapter:
    async def test__get_similar_tracks__nominal(self, gemini_client: GeminiClientAdapter) -> None:
        tracks_suggested = await gemini_client.get_similar_tracks(
            artist_name="dummy-artist",
            track_name="dummy-track",
            limit=5,
        )
        assert len(tracks_suggested) == 1

        track = tracks_suggested[0]
        assert track.name == "Mi Pueblo"
        assert track.artists == ["Grupo Niche"]
        assert track.advisor_id is None
        assert track.score == pytest.approx(1.0)
