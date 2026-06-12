import pytest

from museflow.domain.entities.music import Track
from museflow.domain.exceptions import ProviderPageValidationError
from museflow.domain.types import MusicProvider
from museflow.infrastructure.adapters.providers.spotify.library import SpotifyLibraryAdapter

from tests.integration.factories.models.music import TrackModelFactory
from tests.integration.utils.wiremock import WireMockContext


@pytest.mark.wiremock("spotify")
class TestSpotifyLibrary:
    @pytest.fixture
    async def playlist_tracks(self) -> list[Track]:
        return [
            (await TrackModelFactory.create_async(provider_id=track_id)).to_entity()
            for track_id in ["7J5pB49l9ycy9ImB6D9hu0", "1Fp4njyRHJYyMTKP899c0q", "7eOSOc9z6gcsGBznsg5mk3"]
        ]

    async def test__search__nominal(self, spotify_library: SpotifyLibraryAdapter) -> None:
        tracks = await spotify_library.search_tracks(track="Mi Pueblo", page_size=5)
        assert len(tracks) == 8

        track_first = tracks[0]
        assert track_first.id is not None
        assert track_first.user_id == spotify_library.user.id
        assert track_first.name == "Mi Pueblo"
        assert len(track_first.artists) == 1
        assert track_first.artists[0] == "Grupo Niche"
        assert track_first.provider == MusicProvider.SPOTIFY
        assert track_first.provider_id == "30xocklvViCtxktihAEZM8"
        assert track_first.played_at_last is None

        track_last = tracks[-1]
        assert track_last.id is not None
        assert track_last.user_id == spotify_library.user.id
        assert track_last.name == "Mi Pueblo"
        assert len(track_last.artists) == 1
        assert track_last.artists[0] == "Grupo Niche"
        assert track_last.provider == MusicProvider.SPOTIFY
        assert track_last.provider_id == "0K81HUG9YhPp6khuUEAH9g"
        assert track_last.played_at_last is None

    async def test__search__max_pages(
        self,
        spotify_library: SpotifyLibraryAdapter,
    ) -> None:
        tracks = await spotify_library.search_tracks(track="Mi Pueblo", page_size=5, max_pages=1)
        assert len(tracks) == 5

    async def test__search__page_validation_error(
        self,
        spotify_library: SpotifyLibraryAdapter,
        spotify_wiremock: WireMockContext,
    ) -> None:
        spotify_wiremock.create_mapping(
            method="GET",
            url_path="/search",
            status=200,
            json_body={"no_tracks_key": "unexpected"},
        )

        with pytest.raises(ProviderPageValidationError):
            await spotify_library.search_tracks(track="Mi Pueblo")

    async def test__play_track__nominal(self, spotify_library: SpotifyLibraryAdapter) -> None:
        await spotify_library.play_track("6rqhFgbbKwnb9MLmUQDhG6")

    async def test__create_playlist__nominal(
        self,
        playlist_tracks: list[Track],
        spotify_library: SpotifyLibraryAdapter,
    ) -> None:
        playlist = await spotify_library.create_playlist(name="test", tracks=playlist_tracks)

        assert playlist.id is not None
        assert playlist.user_id == spotify_library.user.id
        assert playlist.name == "test"
        assert playlist.provider == MusicProvider.SPOTIFY
        assert playlist.provider_id == "5ta70oLZcXLReU7bEEXQXy"
        assert playlist.snapshot_id == "AAAAAsNYTkn8k2rpWWck/VOdy+GiqV1c"
        assert playlist.tracks == playlist_tracks
