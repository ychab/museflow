import asyncio
import copy
import json
import logging
from typing import Any
from unittest import mock

import pytest

from spotifagent.domain.entities.auth import OAuthProviderTokenState
from spotifagent.domain.entities.auth import OAuthProviderUserToken
from spotifagent.domain.entities.auth import OAuthProviderUserTokenUpdate
from spotifagent.domain.entities.music import MusicProvider
from spotifagent.domain.entities.users import User
from spotifagent.infrastructure.adapters.providers.spotify.library import SpotifyLibraryAdapter
from spotifagent.infrastructure.adapters.providers.spotify.library import SpotifyLibraryFactory
from spotifagent.infrastructure.config.settings.app import app_settings

from tests import ASSETS_DIR
from tests.unit.factories.auth import OAuthProviderTokenStateFactory


def paginate_response(
    token_state: OAuthProviderTokenState,
    response: dict[str, Any],
    total: int,
    limit: int,
    offset: int = 0,
    size: int | None = None,
) -> list[tuple[dict[str, Any], OAuthProviderTokenState]]:
    side_effects = []

    while offset + limit <= (size or total):
        response_chunk = copy.deepcopy(response)
        response_chunk["offset"] = offset
        response_chunk["limit"] = limit
        response_chunk["total"] = total
        response_chunk["items"] = response_chunk["items"][offset : offset + limit]

        side_effects += [(response_chunk, token_state)]
        offset += limit

    return side_effects


class TestSpotifyLibraryFactory:
    @pytest.fixture
    def spotify_library_factory(
        self,
        mock_auth_token_repository: mock.Mock,
        mock_provider_client: mock.AsyncMock,
    ) -> SpotifyLibraryFactory:
        return SpotifyLibraryFactory(
            auth_token_repository=mock_auth_token_repository,
            client=mock_provider_client,
        )

    def test_create__nominal(
        self,
        user: User,
        auth_token: OAuthProviderUserToken,
        spotify_library_factory: SpotifyLibraryFactory,
    ) -> None:
        spotify_library = spotify_library_factory.create(user, auth_token)
        assert isinstance(spotify_library, SpotifyLibraryAdapter)
        assert spotify_library.user == user
        assert spotify_library.auth_token == auth_token


class TestSpotifyLibrary:
    @pytest.fixture
    def patch_max_concurrency(self, monkeypatch: pytest.MonkeyPatch) -> int:
        max_concurrency: int = 10
        monkeypatch.setattr(app_settings, "SYNC_SEMAPHORE_MAX_CONCURRENCY", max_concurrency)
        return max_concurrency

    @pytest.fixture
    def spotify_library(
        self,
        user: User,
        auth_token: OAuthProviderUserToken,
        patch_max_concurrency: int,
        mock_auth_token_repository: mock.AsyncMock,
        mock_provider_client: mock.AsyncMock,
    ) -> SpotifyLibraryAdapter:
        return SpotifyLibraryAdapter(
            user=user,
            auth_token=auth_token,
            auth_token_repository=mock_auth_token_repository,
            client=mock_provider_client,
            max_concurrency=patch_max_concurrency,
        )

    @pytest.fixture
    def spotify_response(self, request: pytest.FixtureRequest) -> dict[str, Any]:
        filename: str = getattr(request, "param", "top_artists")
        filepath = ASSETS_DIR / "httpmock" / "spotify" / f"{filename}.json"
        return json.loads(filepath.read_text())

    @pytest.fixture
    def spotify_response_pages(
        self,
        request: pytest.FixtureRequest,
        spotify_response: dict[str, Any],
        token_state: OAuthProviderTokenState,
        mock_provider_client: mock.AsyncMock,
    ) -> tuple[int, int]:
        params = getattr(request, "param", {})
        total: int = params.get("total", 20)
        limit: int = params.get("limit", 5)

        mock_provider_client.make_user_api_call.side_effect = paginate_response(
            token_state=token_state,
            response=spotify_response,
            total=total,
            limit=limit,
        )

        return total, limit

    @pytest.fixture
    def spotify_response_playlist_items_pages(
        self,
        request: pytest.FixtureRequest,
        spotify_response_pages: tuple[int, int],
        token_state: OAuthProviderTokenState,
        mock_provider_client: mock.AsyncMock,
    ) -> tuple[int, int]:
        side_effects = list(mock_provider_client.make_user_api_call.side_effect)

        params: dict[str, Any] = getattr(request, "param", {})
        has_duplicates = params.get("has_duplicates", False)

        filepath = ASSETS_DIR / "httpmock" / "spotify" / "playlist_items.json"
        spotify_response = json.loads(filepath.read_text())

        playlist_total = spotify_response_pages[0]
        playlist_limit = spotify_response_pages[1]
        total: int = playlist_limit * 3
        offset: int = 0
        for _ in range(playlist_total):
            side_effects += paginate_response(
                token_state=token_state,
                response=spotify_response,
                total=total,
                limit=playlist_limit,
                offset=offset,
                size=total + offset,
            )

            if not has_duplicates:
                offset += total

        mock_provider_client.make_user_api_call.side_effect = side_effects
        return total, playlist_limit

    @pytest.fixture
    def spotify_response_playlist_items_invalid_pages(
        self,
        token_state: OAuthProviderTokenState,
        mock_provider_client: mock.AsyncMock,
    ) -> None:
        side_effects = list(mock_provider_client.make_user_api_call.side_effect)

        side_effects += [
            (
                {
                    "items": [
                        {
                            "item": {
                                "artists": [{"id": None, "name": ""}],
                                "href": None,
                                "id": None,
                                "name": "my-custom-track-which-dont-exists-on-spotify-db",
                                "popularity": 0,
                            },
                        },
                    ],
                    "limit": 50,
                    "offset": 0,
                    "total": 1,
                },
                token_state,
            ),
        ]
        mock_provider_client.make_user_api_call.side_effect = side_effects

    async def test__execute_request__refreshed_token(
        self,
        spotify_library: SpotifyLibraryAdapter,
        user: User,
        token_state: OAuthProviderTokenState,
        mock_provider_client: mock.AsyncMock,
        mock_auth_token_repository: mock.AsyncMock,
    ) -> None:
        mock_provider_client.make_user_api_call.return_value = ({"data": "ok"}, token_state)

        await spotify_library._execute_request("GET", "/test")

        # Check that user token is refreshed in memory.
        assert spotify_library.auth_token.token_type == token_state.token_type
        assert spotify_library.auth_token.token_access == token_state.access_token
        assert spotify_library.auth_token.token_refresh == token_state.refresh_token
        assert spotify_library.auth_token.token_expires_at == token_state.expires_at

        # Check that user token is refreshed in DB.
        mock_auth_token_repository.update.assert_called_once_with(
            user_id=spotify_library.user.id,
            provider=MusicProvider.SPOTIFY,
            auth_token_data=OAuthProviderUserTokenUpdate(
                token_type=token_state.token_type,
                token_access=token_state.access_token,
                token_refresh=token_state.refresh_token,
                token_expires_at=token_state.expires_at,
            ),
        )

    async def test__execute_request__no_refreshed_token(
        self,
        spotify_library: SpotifyLibraryAdapter,
        user: User,
        mock_provider_client: mock.AsyncMock,
        mock_auth_token_repository: mock.AsyncMock,
    ) -> None:
        token_state_unchanged = OAuthProviderTokenStateFactory.build(
            access_token=spotify_library.auth_token.token_access
        )
        mock_provider_client.refresh_access_token.return_value = token_state_unchanged
        mock_provider_client.make_user_api_call.return_value = ({"data": "ok"}, token_state_unchanged)

        await spotify_library._execute_request("GET", "/test")

        # Check that user token wasn't refreshed in memory.
        assert spotify_library.auth_token.token_access == token_state_unchanged.access_token

        # Check that DB have not been updated.
        mock_auth_token_repository.update.assert_not_called()

    async def test__refresh_token__already_refreshed(
        self,
        spotify_library: SpotifyLibraryAdapter,
        mock_provider_client: mock.AsyncMock,
        mock_auth_token_repository: mock.AsyncMock,
    ) -> None:
        spotify_library._is_token_refreshed = True

        await spotify_library._refresh_token()

        mock_provider_client.refresh_access_token.assert_not_called()
        mock_auth_token_repository.update.assert_not_called()

    async def test__refresh_token__concurrent_calls__executes_once(
        self,
        spotify_library: SpotifyLibraryAdapter,
        patch_max_concurrency: int,
        mock_provider_client: mock.AsyncMock,
        mock_auth_token_repository: mock.AsyncMock,
        token_state: OAuthProviderTokenState,
    ) -> None:
        new_token_state = OAuthProviderTokenStateFactory.build()

        async def delayed_refresh(*args, **kwargs):
            await asyncio.sleep(0.05)  # Simulate network latency
            return new_token_state

        mock_provider_client.refresh_access_token.side_effect = delayed_refresh

        # Launch concurrent calls
        async with asyncio.TaskGroup() as tg:
            for _ in range(patch_max_concurrency):
                tg.create_task(spotify_library._refresh_token())

        mock_provider_client.refresh_access_token.assert_called_once()
        mock_auth_token_repository.update.assert_called_once()

        assert spotify_library._is_token_refreshed is True
        assert spotify_library.auth_token.token_access == new_token_state.access_token

    @pytest.mark.parametrize("spotify_response", ["top_artists"], indirect=["spotify_response"])
    async def test__get_top_artists__nominal(
        self,
        spotify_library: SpotifyLibraryAdapter,
        spotify_response: dict[str, Any],
        spotify_response_pages: tuple[int, int],
    ) -> None:
        top_artists = await spotify_library.get_top_artists(page_limit=spotify_response_pages[1])
        assert len(top_artists) == 20

        top_artist_first = top_artists[0]
        assert top_artist_first.id is not None
        assert top_artist_first.user_id == spotify_library.user.id
        assert top_artist_first.name == "Vald"
        assert top_artist_first.popularity == 68
        assert top_artist_first.is_saved is False
        assert top_artist_first.is_top is True
        assert top_artist_first.top_position == 1
        assert top_artist_first.genres == ["french rap"]
        assert top_artist_first.provider == MusicProvider.SPOTIFY
        assert top_artist_first.provider_id == "3CnCGFxXbOA8bAK54jR8js"

        top_artist_last = top_artists[-1]
        assert top_artist_last.id is not None
        assert top_artist_last.user_id == spotify_library.user.id
        assert top_artist_last.name == "Bad Bunny"
        assert top_artist_last.popularity == 99
        assert top_artist_last.is_saved is False
        assert top_artist_last.is_top is True
        assert top_artist_last.top_position == len(top_artists) == 20
        assert top_artist_last.genres == ["reggaeton", "trap latino", "urbano latino", "latin"]
        assert top_artist_last.provider == MusicProvider.SPOTIFY
        assert top_artist_last.provider_id == "4q3ewBCX7sLwd24euuV69X"

    @pytest.mark.parametrize("spotify_response", ["top_tracks"], indirect=["spotify_response"])
    async def test__get_top_tracks__nominal(
        self,
        spotify_library: SpotifyLibraryAdapter,
        spotify_response: dict[str, Any],
        spotify_response_pages: tuple[int, int],
    ) -> None:
        top_tracks = await spotify_library.get_top_tracks(page_limit=spotify_response_pages[1])
        assert len(top_tracks) == 20

        top_track_first = top_tracks[0]
        assert top_track_first.id is not None
        assert top_track_first.user_id == spotify_library.user.id
        assert top_track_first.name == "La Negra No Quiere"
        assert top_track_first.popularity == 20
        assert top_track_first.is_saved is False
        assert top_track_first.is_top is True
        assert top_track_first.top_position == 1
        assert len(top_track_first.artists) == 1
        assert top_track_first.artists[0].provider_id == "1zng9JZpblpk48IPceRWs8"
        assert top_track_first.artists[0].name == "Grupo Niche"
        assert top_track_first.provider == MusicProvider.SPOTIFY
        assert top_track_first.provider_id == "7J5pB49l9ycy9ImB6D9hu0"

        top_track_last = top_tracks[-1]
        assert top_track_last.id is not None
        assert top_track_last.user_id == spotify_library.user.id
        assert top_track_last.name == "Deux mille"
        assert top_track_last.popularity == 60
        assert top_track_last.is_saved is False
        assert top_track_last.is_top is True
        assert top_track_last.top_position == len(top_tracks) == 20
        assert len(top_track_last.artists) == 1
        assert top_track_last.artists[0].provider_id == "2kXKa3aAFngGz2P4GjG5w2"
        assert top_track_last.artists[0].name == "SCH"
        assert top_track_last.provider == MusicProvider.SPOTIFY
        assert top_track_last.provider_id == "03LDM6VoTJbfdw1L7USDU8"

    @pytest.mark.parametrize("spotify_response", ["saved_tracks"], indirect=["spotify_response"])
    async def test__get_saved_tracks__nominal(
        self,
        spotify_library: SpotifyLibraryAdapter,
        spotify_response: dict[str, Any],
        spotify_response_pages: tuple[int, int],
    ) -> None:
        tracks_saved = await spotify_library.get_saved_tracks(page_limit=spotify_response_pages[1])
        assert len(tracks_saved) == 20

        track_saved_first = tracks_saved[0]
        assert track_saved_first.id is not None
        assert track_saved_first.user_id == spotify_library.user.id
        assert track_saved_first.name == "Honey"
        assert track_saved_first.popularity == 48
        assert track_saved_first.is_saved is True
        assert track_saved_first.is_top is False
        assert track_saved_first.top_position is None
        assert len(track_saved_first.artists) == 1
        assert track_saved_first.artists[0].provider_id == "54kCbQZaZWHnwwj9VP2hn4"
        assert track_saved_first.artists[0].name == "Zola"
        assert track_saved_first.provider == MusicProvider.SPOTIFY
        assert track_saved_first.provider_id == "5GZPHysxDmjSAtXN87D78S"

        track_saved_last = tracks_saved[-1]
        assert track_saved_last.id is not None
        assert track_saved_last.user_id == spotify_library.user.id
        assert track_saved_last.name == "Magnum"
        assert track_saved_last.popularity == 36
        assert track_saved_last.is_saved is True
        assert track_saved_last.is_top is False
        assert track_saved_last.top_position is None
        assert len(track_saved_last.artists) == 1
        assert track_saved_last.artists[0].provider_id == "2kXKa3aAFngGz2P4GjG5w2"
        assert track_saved_last.artists[0].name == "SCH"
        assert track_saved_last.provider == MusicProvider.SPOTIFY
        assert track_saved_last.provider_id == "4nKcfnZ2Qj5urw0ekrnF2M"

    @pytest.mark.parametrize(
        ("spotify_response", "spotify_response_pages"),
        [("playlists", {"total": 4, "limit": 2})],
        indirect=["spotify_response", "spotify_response_pages"],
    )
    async def test__get_playlist_tracks__duplicate__none(
        self,
        spotify_library: SpotifyLibraryAdapter,
        spotify_response: dict[str, Any],
        spotify_response_pages: tuple[int, int],
        spotify_response_playlist_items_pages: tuple[int, int],
    ) -> None:
        playlist_total = spotify_response_pages[0]
        playlist_tracks_total = spotify_response_playlist_items_pages[0]

        tracks = await spotify_library.get_playlist_tracks(page_limit=spotify_response_pages[1])
        assert len(tracks) == playlist_total * playlist_tracks_total

        track_first = tracks[0]
        assert track_first.id is not None
        assert track_first.user_id == spotify_library.user.id
        assert track_first.name == "El Preso"
        assert track_first.popularity == 0
        assert track_first.is_saved is False
        assert track_first.is_top is False
        assert track_first.top_position is None
        assert len(track_first.artists) == 1
        assert track_first.artists[0].provider_id == "5aAlzehdUM14I4ppq24Xob"
        assert track_first.artists[0].name == "Fruko Y Sus Tesos"
        assert track_first.provider == MusicProvider.SPOTIFY
        assert track_first.provider_id == "69LfSVCs3xfpwLiS6c0q4E"

        track_last = tracks[-1]
        assert track_last.id is not None
        assert track_last.user_id == spotify_library.user.id
        assert track_last.name == "Con la Punta del Pie"
        assert track_last.popularity == 56
        assert track_last.is_saved is False
        assert track_last.is_top is False
        assert track_last.top_position is None
        assert len(track_last.artists) == 1
        assert track_last.artists[0].provider_id == "4dCNiyQXmtiWA157q3uFyj"
        assert track_last.artists[0].name == "La Gloria Matancera"
        assert track_last.provider == MusicProvider.SPOTIFY
        assert track_last.provider_id == "4rt2zpNhFBayp948Pi6liZ"

    @pytest.mark.parametrize(
        ("spotify_response", "spotify_response_pages", "spotify_response_playlist_items_pages"),
        [("playlists", {"total": 4, "limit": 2}, {"has_duplicates": True})],
        indirect=["spotify_response", "spotify_response_pages", "spotify_response_playlist_items_pages"],
    )
    async def test__get_playlist_tracks__duplicate(
        self,
        spotify_library: SpotifyLibraryAdapter,
        spotify_response: dict[str, Any],
        spotify_response_pages: tuple[int, int],
        spotify_response_playlist_items_pages: tuple[int, int],
    ) -> None:
        playlist_tracks_total = spotify_response_playlist_items_pages[0]

        tracks = await spotify_library.get_playlist_tracks(page_limit=spotify_response_pages[1])
        assert len(tracks) == playlist_tracks_total

        track_first = tracks[0]
        assert track_first.id is not None
        assert track_first.user_id == spotify_library.user.id
        assert track_first.name == "El Preso"
        assert track_first.popularity == 0
        assert track_first.is_saved is False
        assert track_first.is_top is False
        assert track_first.top_position is None
        assert len(track_first.artists) == 1
        assert track_first.artists[0].provider_id == "5aAlzehdUM14I4ppq24Xob"
        assert track_first.artists[0].name == "Fruko Y Sus Tesos"
        assert track_first.provider == MusicProvider.SPOTIFY
        assert track_first.provider_id == "69LfSVCs3xfpwLiS6c0q4E"

        track_last = tracks[-1]
        assert track_last.id is not None
        assert track_last.user_id == spotify_library.user.id
        assert track_last.name == "Micaela"
        assert track_last.popularity == 54
        assert track_last.is_saved is False
        assert track_last.is_top is False
        assert track_last.top_position is None
        assert len(track_last.artists) == 2
        assert track_last.artists[0].provider_id == "34qU0b0yRjEzRJtknerEDS"
        assert track_last.artists[0].name == "Sonora Carruseles"
        assert track_last.artists[1].provider_id == "125qXSgsP3irn2SEE6rpor"
        assert track_last.artists[1].name == "Luis Florez"
        assert track_last.provider == MusicProvider.SPOTIFY
        assert track_last.provider_id == "1m3paVx65imhvCjPx505Oy"

    @pytest.mark.parametrize(
        ("spotify_response", "spotify_response_pages"),
        [("playlists", {"total": 1, "limit": 1})],
        indirect=["spotify_response", "spotify_response_pages"],
    )
    async def test__get_playlist_tracks__page_validation_error(
        self,
        spotify_library: SpotifyLibraryAdapter,
        spotify_response: dict[str, Any],
        spotify_response_pages: tuple[int, int],
        spotify_response_playlist_items_invalid_pages: None,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        playlist = spotify_response["items"][0]

        with caplog.at_level(logging.ERROR):
            tracks = await spotify_library.get_playlist_tracks(page_limit=1)
        assert len(tracks) == 0

        prefix_log = f"[PlaylistTracks({playlist['name']})]"
        exc_msg = f"{prefix_log} - Page validation error on /playlists/{playlist['id']}/items (offset: 0): "
        assert f"Skip playlist {playlist['name'].strip()} with error: {exc_msg}" in caplog.text
        assert "3 validation errors for SpotifyPlaylistTrackPage" in caplog.text
        assert "items.0.item.id\n  Input should be a valid string" in caplog.text
        assert "items.0.item.href\n  URL input should be a string or URL" in caplog.text
        assert "items.0.item.artists.0.id\n  Input should be a valid string" in caplog.text
