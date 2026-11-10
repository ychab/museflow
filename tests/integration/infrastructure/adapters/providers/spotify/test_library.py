import logging

import pytest

from museflow.domain.entities.track import Track
from museflow.domain.enums import MusicProvider
from museflow.domain.enums import PlaylistType
from museflow.domain.exceptions import ProviderPageValidationError
from museflow.domain.exceptions import ProviderSearchQueryInvalidError
from museflow.infrastructure.adapters.providers.spotify.library import SpotifyLibraryAdapter

from tests.integration.factories.models.track import TrackModelFactory
from tests.integration.utils.wiremock import WireMockContext

EMPTY_SEARCH_PAGE = {
    "tracks": {"href": "", "limit": 10, "next": None, "offset": 0, "previous": None, "total": 0, "items": []}
}


@pytest.mark.wiremock("spotify")
class TestSpotifyLibrary:
    @pytest.fixture
    async def playlist_tracks(self) -> list[Track]:
        return [
            await TrackModelFactory.create_entity_async(
                provider_links=[{"provider": MusicProvider.SPOTIFY.value, "provider_id": track_id}]
            )
            for track_id in ["7J5pB49l9ycy9ImB6D9hu0", "1Fp4njyRHJYyMTKP899c0q", "7eOSOc9z6gcsGBznsg5mk3"]
        ]

    async def test__search_artist_tracks__page_validation_error(
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
            await spotify_library.search_artist_tracks(artist="Grupo Niche", max_pages=1)

    async def test__search_artist_tracks__query_invalid(
        self,
        spotify_library: SpotifyLibraryAdapter,
        spotify_wiremock: WireMockContext,
    ) -> None:
        spotify_wiremock.create_mapping(
            method="GET",
            url_path="/search",
            status=400,
            json_body={"error": {"status": 400, "message": "Bad request."}},
        )

        with pytest.raises(ProviderSearchQueryInvalidError, match="Spotify rejected the search query for artist"):
            await spotify_library.search_artist_tracks(artist="Caf\x00\x19", max_pages=1)

    async def test__search_artist_tracks__nominal(
        self,
        spotify_library: SpotifyLibraryAdapter,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """A short first page does not end the search: the pages are read up to `max_pages`."""
        with caplog.at_level(logging.DEBUG):
            tracks = await spotify_library.search_artist_tracks(artist="Grupo Niche", max_pages=2)

        # 5 tracks on the first page of 10, then 3 more on the next one.
        assert len(tracks) == 8
        assert [message for message in caplog.messages if message.startswith("Search query")] == [
            "Search query 'artist:\"Grupo Niche\"' returned 8 track(s)",
        ]
        assert [(track.name, track.album_name, track.album_year) for track in tracks[:2]] == [
            ("Mi Pueblo", "The Best", 1988),
            ("Mi Pueblo", "Llegando Al 100%", 1992),
        ]

    async def test__search_artist_tracks__empty_page__stops(
        self,
        spotify_library: SpotifyLibraryAdapter,
        spotify_wiremock: WireMockContext,
    ) -> None:
        spotify_wiremock.create_mapping(
            method="GET",
            url_path="/search",
            status=200,
            query_params={"q": 'artist:"Grupo Niche"', "offset": 20},
            json_body=EMPTY_SEARCH_PAGE,
        )

        tracks = await spotify_library.search_artist_tracks(artist="Grupo Niche", max_pages=10)

        assert len(tracks) == 8

    async def test__play_track__nominal(self, spotify_library: SpotifyLibraryAdapter) -> None:
        await spotify_library.play_track("6rqhFgbbKwnb9MLmUQDhG6")

    async def test__create_playlist__nominal(
        self,
        playlist_tracks: list[Track],
        spotify_library: SpotifyLibraryAdapter,
    ) -> None:
        playlist = await spotify_library.create_playlist(
            name="test",
            type=PlaylistType.DISCOVERY,
            tracks=playlist_tracks,
        )

        assert playlist.id is not None
        assert playlist.user_id == spotify_library.user.id
        assert playlist.name == "test"
        assert playlist.provider == MusicProvider.SPOTIFY
        assert playlist.provider_id == "5ta70oLZcXLReU7bEEXQXy"
        assert playlist.snapshot_id == "AAAAAsNYTkn8k2rpWWck/VOdy+GiqV1c"
        assert playlist.tracks == playlist_tracks
        assert playlist.type == PlaylistType.DISCOVERY
