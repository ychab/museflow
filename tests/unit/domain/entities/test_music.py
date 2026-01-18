from spotifagent.domain.entities.music import TopArtist
from spotifagent.domain.entities.music import TopTrack
from spotifagent.domain.entities.music import TopTrackArtist
from spotifagent.domain.entities.users import User


class TestTopArtist:
    def test__slug__computed(self, user: User) -> None:
        top_artist = TopArtist(
            user_id=user.id,
            name="Yé hô",
            popularity=50,
            position=1,
            provider_id="foo",
            genres=["Pop"],
        )
        assert top_artist.slug == "ye-ho"


class TestTopTrack:
    def test__slug__computed(self, user: User) -> None:
        top_artist = TopTrack(
            user_id=user.id,
            name="Yé hô",
            popularity=50,
            position=1,
            provider_id="foo",
            artists=[TopTrackArtist(provider_id="foo", name="foo")],
        )
        assert top_artist.slug == "ye-ho"
