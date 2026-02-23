from unittest import mock

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import pytest

from spotifagent.application.services.spotify import SpotifyUserSession
from spotifagent.domain.entities.auth import OAuthProviderTokenState
from spotifagent.domain.entities.auth import OAuthProviderUserToken
from spotifagent.domain.entities.music import MusicProvider
from spotifagent.domain.entities.users import User
from spotifagent.domain.ports.providers.client import ProviderOAuthClientPort
from spotifagent.domain.ports.repositories.auth import OAuthProviderTokenRepositoryPort
from spotifagent.infrastructure.adapters.database.models import AuthProviderToken as AuthProviderTokenModel


class TestSpotifyUserSession:
    @pytest.fixture
    def mock_spotify_client(self) -> mock.AsyncMock:
        return mock.AsyncMock(spec=ProviderOAuthClientPort)

    @pytest.fixture
    def spotify_session(
        self,
        user: User,
        auth_token: OAuthProviderUserToken,
        auth_token_repository: OAuthProviderTokenRepositoryPort,
        mock_spotify_client: mock.AsyncMock,
    ) -> SpotifyUserSession:
        return SpotifyUserSession(
            user=user,
            auth_token=auth_token,
            auth_token_repository=auth_token_repository,
            client=mock_spotify_client,
        )

    async def test__execute_request__persists_new_token(
        self,
        spotify_session: SpotifyUserSession,
        user: User,
        token_state: OAuthProviderTokenState,
        auth_token: OAuthProviderUserToken,
        mock_spotify_client: mock.AsyncMock,
        async_session_db: AsyncSession,
    ) -> None:
        mock_spotify_client.refresh_access_token.return_value = token_state
        mock_spotify_client.make_user_api_call.return_value = ({"data": "ok"}, token_state)

        await spotify_session._execute_request("GET", "/test")

        # Check that user token is refresh in memory.
        assert spotify_session.auth_token.token_type == token_state.token_type
        assert spotify_session.auth_token.token_access == token_state.access_token
        assert spotify_session.auth_token.token_refresh == token_state.refresh_token
        assert spotify_session.auth_token.token_expires_at == token_state.expires_at

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
