import json
import logging
from typing import Any

import pytest

from museflow.domain.entities.music import Track
from museflow.domain.exceptions import ProviderPageValidationError
from museflow.domain.types import MusicProvider
from museflow.infrastructure.adapters.providers.spotify.library import SpotifyLibraryAdapter

from tests import ASSETS_DIR
from tests.integration.factories.models.music import TrackModelFactory
from tests.integration.utils.wiremock import WireMockContext


@pytest.mark.wiremock("spotify")
class TestSpotifyLibrary:
    @pytest.fixture
    def track_locale(self) -> dict[str, Any]:
        return {
            "id": None,
            "name": "local-file",
            "href": None,
            "is_local": True,
            "artists": [
                {
                    "id": None,
                    "name": "",
                },
            ],
        }

    @pytest.fixture
    def wiremock_response(self, request: pytest.FixtureRequest) -> dict[str, Any]:
        filename = getattr(request, "param", "")
        filepath = ASSETS_DIR / "wiremock" / "spotify" / "__files" / f"{filename}.json"
        return json.loads(filepath.read_text())

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
        assert track_first.artists[0].provider_id == "1zng9JZpblpk48IPceRWs8"
        assert track_first.artists[0].name == "Grupo Niche"
        assert track_first.provider == MusicProvider.SPOTIFY
        assert track_first.provider_id == "30xocklvViCtxktihAEZM8"
        assert track_first.played_at is None

        track_last = tracks[-1]
        assert track_last.id is not None
        assert track_last.user_id == spotify_library.user.id
        assert track_last.name == "Mi Pueblo"
        assert len(track_last.artists) == 1
        assert track_last.artists[0].provider_id == "1zng9JZpblpk48IPceRWs8"
        assert track_last.artists[0].name == "Grupo Niche"
        assert track_last.provider == MusicProvider.SPOTIFY
        assert track_last.provider_id == "0K81HUG9YhPp6khuUEAH9g"
        assert track_last.played_at is None

    async def test__get_track_by_id__nominal(self, spotify_library: SpotifyLibraryAdapter) -> None:
        track = await spotify_library.get_track_by_id(track_id="7J5pB49l9ycy9ImB6D9hu0")

        assert track.id is not None
        assert track.user_id == spotify_library.user.id
        assert track.name == "La Negra No Quiere"
        assert track.provider_id == "7J5pB49l9ycy9ImB6D9hu0"
        assert len(track.artists) == 1
        assert track.artists[0].provider_id == "1zng9JZpblpk48IPceRWs8"
        assert track.artists[0].name == "Grupo Niche"
        assert track.isrc == "COC018416252"
        assert track.played_at is None

    async def test__get_tracks_by_ids__nominal(self, spotify_library: SpotifyLibraryAdapter) -> None:
        tracks = await spotify_library.get_tracks_by_ids(
            track_ids=[
                "7J5pB49l9ycy9ImB6D9hu0",
                "4BqYFb5LHhRmmTDsPyUmQg",
            ]
        )

        assert len(tracks) == 2
        assert tracks[0].provider_id == "7J5pB49l9ycy9ImB6D9hu0"
        assert tracks[1].provider_id == "4BqYFb5LHhRmmTDsPyUmQg"

    @pytest.mark.parametrize("wiremock_response", ["track_4BqYFb5LHhRmmTDsPyUmQg"], indirect=["wiremock_response"])
    async def test__get_tracks_by_ids__skips__none(
        self,
        spotify_library: SpotifyLibraryAdapter,
        spotify_wiremock: WireMockContext,
        wiremock_response: dict[str, Any],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        spotify_wiremock.create_mapping(
            method="GET",
            url_path="/tracks",
            status=200,
            json_body={"tracks": [None, wiremock_response]},
        )

        with caplog.at_level(logging.DEBUG):
            tracks = await spotify_library.get_tracks_by_ids(
                track_ids=[
                    "id_not_exists",
                    "4BqYFb5LHhRmmTDsPyUmQg",
                ]
            )

        assert len(tracks) == 1
        assert tracks[0].provider_id == "4BqYFb5LHhRmmTDsPyUmQg"

        assert "Skipping null track entry in response" in caplog.text

    @pytest.mark.parametrize("wiremock_response", ["track_4BqYFb5LHhRmmTDsPyUmQg"], indirect=["wiremock_response"])
    async def test__get_tracks_by_ids__skips__local_file(
        self,
        spotify_library: SpotifyLibraryAdapter,
        track_locale: dict[str, Any],
        wiremock_response: dict[str, Any],
        spotify_wiremock: WireMockContext,
    ) -> None:
        spotify_wiremock.create_mapping(
            method="GET",
            url_path="/tracks",
            status=200,
            json_body={"tracks": [track_locale, wiremock_response]},
        )

        tracks = await spotify_library.get_tracks_by_ids(
            track_ids=[
                "local_id",
                "4BqYFb5LHhRmmTDsPyUmQg",
            ]
        )

        assert len(tracks) == 1
        assert tracks[0].provider_id == "4BqYFb5LHhRmmTDsPyUmQg"

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
