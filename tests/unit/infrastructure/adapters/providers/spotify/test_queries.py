from museflow.infrastructure.adapters.providers.spotify.queries import SpotifySearchArtistQuery


class TestSpotifySearchArtistQuery:
    def test__query__escaped(self) -> None:
        assert SpotifySearchArtistQuery(artist='The "Band"').get_query() == 'artist:"The \\"Band\\""'
