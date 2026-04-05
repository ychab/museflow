import pytest

from museflow.infrastructure.adapters.advisors.gemini.schemas import GeminiSuggestedTrack
from museflow.infrastructure.adapters.advisors.gemini.schemas import GeminiSuggestedTracksContent


class TestGeminiSuggestedTracksContent:
    def test__parse__nominal(self) -> None:
        data = {"tracks": [{"name": "Mi Pueblo", "artists": ["Grupo Niche"], "score": 0.95}]}
        content = GeminiSuggestedTracksContent.model_validate(data)
        assert len(content.tracks) == 1
        assert content.tracks[0].name == "Mi Pueblo"
        assert content.tracks[0].artists == ["Grupo Niche"]
        assert content.tracks[0].score == pytest.approx(0.95)

    def test__parse__empty_tracks(self) -> None:
        data: dict[str, list[object]] = {"tracks": []}
        content = GeminiSuggestedTracksContent.model_validate(data)
        assert content.tracks == []


class TestGeminiSuggestedTrack:
    def test__parse__multiple_artists(self) -> None:
        track = GeminiSuggestedTrack.model_validate({"name": "Song", "artists": ["A", "B"], "score": 0.5})
        assert track.artists == ["A", "B"]
