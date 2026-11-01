import pytest

from museflow.infrastructure.adapters.advisors.openrouter.mappers import to_track_suggested
from museflow.infrastructure.adapters.advisors.openrouter.schemas import SuggestedTrack


class TestToTrackSuggested:
    def test__nominal(self) -> None:
        track = SuggestedTrack(name="Mi Pueblo", artists=["Grupo Niche"], score=0.8)
        result = to_track_suggested(track)
        assert result.name == "Mi Pueblo"
        assert result.artists == ["Grupo Niche"]
        assert result.advisor_id is None
        assert result.score == pytest.approx(0.8)

    def test__score_clamped_above_one(self) -> None:
        track = SuggestedTrack(name="Song", artists=["Artist"], score=1.5)
        result = to_track_suggested(track)
        assert result.score == pytest.approx(1.0)

    def test__score_clamped_below_zero(self) -> None:
        track = SuggestedTrack(name="Song", artists=["Artist"], score=-0.3)
        result = to_track_suggested(track)
        assert result.score == pytest.approx(0.0)

    def test__score_boundary_zero(self) -> None:
        track = SuggestedTrack(name="Song", artists=["Artist"], score=0.0)
        result = to_track_suggested(track)
        assert result.score == pytest.approx(0.0)

    def test__score_boundary_one(self) -> None:
        track = SuggestedTrack(name="Song", artists=["Artist"], score=1.0)
        result = to_track_suggested(track)
        assert result.score == pytest.approx(1.0)

    def test__multiple_artists(self) -> None:
        track = SuggestedTrack(name="Song", artists=["A", "B", "C"], score=0.5)
        result = to_track_suggested(track)
        assert result.artists == ["A", "B", "C"]
