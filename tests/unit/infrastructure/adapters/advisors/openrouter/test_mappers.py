import pytest

from museflow.infrastructure.adapters.advisors.openrouter.mappers import to_discovery_artist_strategy
from museflow.infrastructure.adapters.advisors.openrouter.mappers import to_discovery_strategy
from museflow.infrastructure.adapters.advisors.openrouter.mappers import to_track_suggested
from museflow.infrastructure.adapters.advisors.openrouter.mappers import to_tracks_picked
from museflow.infrastructure.adapters.advisors.openrouter.schemas import DiscoveryArtistsResponse
from museflow.infrastructure.adapters.advisors.openrouter.schemas import DiscoveryPicksResponse
from museflow.infrastructure.adapters.advisors.openrouter.schemas import DiscoveryStrategyResponse
from museflow.infrastructure.adapters.advisors.openrouter.schemas import PickedTrack
from museflow.infrastructure.adapters.advisors.openrouter.schemas import SuggestedArtist
from museflow.infrastructure.adapters.advisors.openrouter.schemas import SuggestedTrack

from tests.unit.factories.entities.track import TrackFactory


class TestToTrackSuggested:
    def test__nominal(self) -> None:
        track = SuggestedTrack(name="Mi Pueblo", artists=["Grupo Niche"], score=0.8)
        result = to_track_suggested(track)
        assert result is not None
        assert result.name == "Mi Pueblo"
        assert result.artists == ["Grupo Niche"]
        assert result.advisor_id is None
        assert result.score == pytest.approx(0.8)

    def test__score_clamped_above_one(self) -> None:
        track = SuggestedTrack(name="Song", artists=["Artist"], score=1.5)
        result = to_track_suggested(track)
        assert result is not None
        assert result.score == pytest.approx(1.0)

    def test__score_clamped_below_zero(self) -> None:
        track = SuggestedTrack(name="Song", artists=["Artist"], score=-0.3)
        result = to_track_suggested(track)
        assert result is not None
        assert result.score == pytest.approx(0.0)

    def test__score_boundary_zero(self) -> None:
        track = SuggestedTrack(name="Song", artists=["Artist"], score=0.0)
        result = to_track_suggested(track)
        assert result is not None
        assert result.score == pytest.approx(0.0)

    def test__score_boundary_one(self) -> None:
        track = SuggestedTrack(name="Song", artists=["Artist"], score=1.0)
        result = to_track_suggested(track)
        assert result is not None
        assert result.score == pytest.approx(1.0)

    def test__multiple_artists(self) -> None:
        track = SuggestedTrack(name="Song", artists=["A", "B", "C"], score=0.5)
        result = to_track_suggested(track)
        assert result is not None
        assert result.artists == ["A", "B", "C"]

    def test__control_chars_stripped(self) -> None:
        track = SuggestedTrack(name="Caf\x00\x19", artists=["The\x1bBand", "\x00"], score=0.5)
        result = to_track_suggested(track)
        assert result is not None
        assert result.name == "Caf"
        assert result.artists == ["The Band"]

    @pytest.mark.parametrize(
        ("name", "artists"),
        [
            pytest.param("\x00\x19", ["Artist"], id="name"),
            pytest.param("Song", ["\x00", "\x19"], id="artists"),
        ],
    )
    def test__only_control_chars__none(self, name: str, artists: list[str]) -> None:
        assert to_track_suggested(SuggestedTrack(name=name, artists=artists, score=0.5)) is None


class TestToDiscoveryStrategy:
    def test__only_control_chars__track_dropped(self) -> None:
        content = DiscoveryStrategyResponse(
            reasoning="reasoning",
            strategy_label="label",
            recommended_tracks=[
                SuggestedTrack(name="\x00", artists=["Artist"], score=0.5),
                SuggestedTrack(name="Song", artists=["Artist"], score=0.5),
            ],
            suggested_playlist_name="name",
        )
        result = to_discovery_strategy(content)
        assert [t.name for t in result.recommended_tracks] == ["Song"]


class TestToDiscoveryArtistStrategy:
    def test__nominal(self) -> None:
        content = DiscoveryArtistsResponse(
            reasoning="reasoning",
            strategy_label="label",
            recommended_artists=[
                SuggestedArtist(name="\x00\x19", sound="sound", score=0.9),
                SuggestedArtist(name="The\x1bBand", sound="Warm brass", score=1.4),
            ],
            suggested_playlist_name="name",
        )

        result = to_discovery_artist_strategy(content)

        # A name of control characters only has nothing to search: dropped.
        assert [(a.name, a.sound, a.score) for a in result.artists] == [("The Band", "Warm brass", 1.0)]


class TestToTracksPicked:
    def test__nominal(self) -> None:
        first, second = TrackFactory.batch(2)
        content = DiscoveryPicksResponse(
            picks=[
                PickedTrack(id=" 2 ", score=0.8),
                PickedTrack(id="99", score=0.9),
                PickedTrack(id="2", score=0.7),
                PickedTrack(id="1", score=-0.2),
            ]
        )

        result = to_tracks_picked(content, candidates={"1": first, "2": second})

        # A made-up id and a second pick of the same id are dropped.
        assert [(tp.track, tp.score) for tp in result] == [(second, 0.8), (first, 0.0)]
