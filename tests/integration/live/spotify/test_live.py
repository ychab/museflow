from collections.abc import AsyncGenerator

import pytest

from museflow.domain.entities.user import User
from museflow.domain.mappers.auth import auth_token_create_from_token_payload
from museflow.domain.ports.repositories.auth import OAuthProviderTokenRepository
from museflow.domain.types import MusicProvider
from museflow.infrastructure.adapters.providers.spotify.client import SpotifyOAuthClientAdapter
from museflow.infrastructure.adapters.providers.spotify.library import SpotifyLibraryAdapter
from museflow.infrastructure.adapters.providers.spotify.session import SpotifyOAuthSessionClient
from museflow.infrastructure.entrypoints.cli.dependencies import get_spotify_client


@pytest.mark.spotify_live
class TestSpotifyLibraryLive:
    """
    This optional live test class checks the integration of the Spotify Client against a live Spotify server.

    To run it manually:
    * first run the database
    * connect a user account to Spotify and manually copy its real refresh token from the DB

    Then execute:
    > SPOTIFY_CLIENT_ID=<REAL_CLIENT_ID> SPOTIFY_CLIENT_SECRET=<REAL_CLIENT_SECRET> poetry run pytest ./tests/integration/live --spotify-refresh-token=<REFRESH_TOKEN>
    """

    @pytest.fixture
    def spotify_refresh_token(self, request: pytest.FixtureRequest) -> str:
        token = request.config.getoption("--spotify-refresh-token")
        if not token:
            pytest.skip("Skipping live Spotify tests (missing token)")
        return token

    @pytest.fixture
    async def spotify_client_live(self) -> AsyncGenerator[SpotifyOAuthClientAdapter]:
        async with get_spotify_client() as client:
            yield client

    @pytest.fixture
    async def spotify_session_live(
        self,
        user: User,
        auth_token_repository: OAuthProviderTokenRepository,
        spotify_refresh_token: str,
        spotify_client_live: SpotifyOAuthClientAdapter,
    ) -> SpotifyOAuthSessionClient:
        token_payload = await spotify_client_live.refresh_access_token(spotify_refresh_token)

        auth_token = await auth_token_repository.create(
            user_id=user.id,
            provider=MusicProvider.SPOTIFY,
            auth_token_data=auth_token_create_from_token_payload(token_payload),
        )

        return SpotifyOAuthSessionClient(
            user=user,
            auth_token=auth_token,
            auth_token_repository=auth_token_repository,
            client=spotify_client_live,
        )

    @pytest.fixture
    def spotify_library_live(
        self, user: User, spotify_session_live: SpotifyOAuthSessionClient
    ) -> SpotifyLibraryAdapter:
        return SpotifyLibraryAdapter(user=user, session_client=spotify_session_live)

    async def test_top_artists(self, spotify_library_live: SpotifyLibraryAdapter) -> None:
        top_artists = await spotify_library_live.get_top_artists(page_size=5, max_pages=1)
        assert len(top_artists) == 5

    async def test_top_tracks(self, spotify_library_live: SpotifyLibraryAdapter) -> None:
        top_tracks = await spotify_library_live.get_top_tracks(page_size=5, max_pages=1)
        assert len(top_tracks) == 5

    async def test_saved_tracks(self, spotify_library_live: SpotifyLibraryAdapter) -> None:
        saved_tracks = await spotify_library_live.get_saved_tracks(page_size=5, max_pages=1)
        assert len(saved_tracks) == 5

    async def test_playlist_tracks(self, spotify_library_live: SpotifyLibraryAdapter) -> None:
        playlist_tracks = await spotify_library_live.get_playlist_tracks(page_size=2, max_pages=1)
        assert len(playlist_tracks) == 2 * (2 * 1)
