from museflow.infrastructure.adapters.advisors.openrouter.mappers import to_discovery_artist_strategy
from museflow.infrastructure.adapters.advisors.openrouter.mappers import to_tracks_picked
from museflow.infrastructure.adapters.advisors.openrouter.schemas import DiscoveryArtistsResponse
from museflow.infrastructure.adapters.advisors.openrouter.schemas import DiscoveryPicksResponse
from museflow.infrastructure.adapters.advisors.openrouter.schemas import PickedTrack
from museflow.infrastructure.adapters.advisors.openrouter.schemas import SuggestedArtist

from tests.unit.factories.entities.track import TrackFactory


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
