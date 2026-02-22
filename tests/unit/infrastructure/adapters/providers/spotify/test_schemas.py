from spotifagent.infrastructure.adapters.providers.spotify.schemas import SpotifyScope


class TestSpotifyScope:
    def test_required_scopes(self) -> None:
        assert SpotifyScope.required_scopes() == "user-top-read user-library-read playlist-read-private"
