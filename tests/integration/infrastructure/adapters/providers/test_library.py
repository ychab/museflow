from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pytest_httpx import HTTPXMock

from spotifagent.domain.entities.auth import OAuthProviderTokenState
from spotifagent.domain.entities.auth import OAuthProviderUserToken
from spotifagent.domain.entities.music import MusicProvider
from spotifagent.domain.entities.users import User
from spotifagent.infrastructure.adapters.database.models import AuthProviderToken as AuthProviderTokenModel
from spotifagent.infrastructure.adapters.providers.spotify.library import SpotifyLibraryAdapter


class TestSpotifyLibrary:
    async def test__execute_request__persists_new_token(
        self,
        async_session_db: AsyncSession,
        frozen_time: datetime,
        spotify_library: SpotifyLibraryAdapter,
        user: User,
        token_state: OAuthProviderTokenState,
        auth_token: OAuthProviderUserToken,
        httpx_mock: HTTPXMock,
    ) -> None:
        httpx_mock.add_response(
            url=str(spotify_library.client.token_endpoint),
            method="POST",
            json={
                "token_type": token_state.token_type,
                "access_token": token_state.access_token,
                "refresh_token": token_state.refresh_token,
                "expires_in": 3600,
            },
        )
        httpx_mock.add_response(
            url=f"{spotify_library.client.base_url}/test",
            method="GET",
            json={"status": "ok"},
        )

        await spotify_library._execute_request("GET", "/test")

        # Check that user token is refresh in memory.
        assert spotify_library.auth_token.token_type == token_state.token_type
        assert spotify_library.auth_token.token_access == token_state.access_token
        assert spotify_library.auth_token.token_refresh == token_state.refresh_token
        assert spotify_library.auth_token.token_expires_at == token_state.expires_at

        # Check that user token is refresh in DB.
        stmt = select(AuthProviderTokenModel).where(
            AuthProviderTokenModel.user_id == user.id,
            AuthProviderTokenModel.provider == MusicProvider.SPOTIFY,
        )
        result = await async_session_db.execute(stmt)
        auth_token_db = result.scalar_one()

        assert auth_token_db is not None
        assert auth_token_db.token_type == token_state.token_type
        assert auth_token_db.token_access == token_state.access_token
        assert auth_token_db.token_refresh == token_state.refresh_token
        assert auth_token_db.token_expires_at == token_state.expires_at
