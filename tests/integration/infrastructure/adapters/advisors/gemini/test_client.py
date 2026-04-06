import pytest

from museflow.infrastructure.adapters.advisors.gemini.client import GeminiAdvisorAdapter


@pytest.mark.wiremock("gemini")
class TestGeminiAdvisorAdapter:
    async def test__get_similar_tracks__nominal(self, gemini_advisor: GeminiAdvisorAdapter) -> None:
        tracks_suggested = await gemini_advisor.get_similar_tracks(
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
