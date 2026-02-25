from datetime import datetime
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import pytest
from pytest_httpx import HTTPXMock

from museflow.application.use_cases.provider_oauth_callback import oauth_callback
from museflow.domain.entities.auth import OAuthProviderTokenState
from museflow.domain.entities.auth import OAuthProviderUserToken
from museflow.domain.entities.music import MusicProvider
from museflow.domain.entities.users import User
from museflow.domain.ports.repositories.auth import OAuthProviderTokenRepositoryPort
from museflow.infrastructure.adapters.database.models import AuthProviderState as AuthProviderStateModel
from museflow.infrastructure.adapters.database.models import AuthProviderToken as AuthProviderTokenModel
from museflow.infrastructure.adapters.providers.spotify.client import SpotifyOAuthClientAdapter


class TestSpotifyOauthCallbackUseCase:
    async def test__token_state__create(
        self,
        async_session_db: AsyncSession,
        frozen_time: datetime,
        user: User,
        token_state: OAuthProviderTokenState,
        auth_token_repository: OAuthProviderTokenRepositoryPort,
        spotify_client: SpotifyOAuthClientAdapter,
        httpx_mock: HTTPXMock,
    ) -> None:
        httpx_mock.add_response(
            url=str(spotify_client.token_endpoint),
            method="POST",
            json={
                "token_type": token_state.token_type,
                "access_token": token_state.access_token,
                "refresh_token": token_state.refresh_token,
                "expires_in": 3600,
            },
        )

        await oauth_callback(
            code="foo",
            user=user,
            provider=MusicProvider.SPOTIFY,
            auth_token_repository=auth_token_repository,
            provider_client=spotify_client,
        )

        stmt_state = select(AuthProviderStateModel).where(
            AuthProviderStateModel.user_id == user.id,
            AuthProviderStateModel.provider == MusicProvider.SPOTIFY,
        )
        result_state = await async_session_db.execute(stmt_state)
        auth_state_db = result_state.scalar_one_or_none()
        assert auth_state_db is None

        stmt_token = select(AuthProviderTokenModel).where(
            AuthProviderTokenModel.user_id == user.id,
            AuthProviderTokenModel.provider == MusicProvider.SPOTIFY,
        )
        result_token = await async_session_db.execute(stmt_token)
        auth_token_db = result_token.scalar_one_or_none()

        assert auth_token_db is not None
        assert auth_token_db.token_type == token_state.token_type
        assert auth_token_db.token_access == token_state.access_token
        assert auth_token_db.token_refresh == token_state.refresh_token
        assert auth_token_db.token_expires_at == frozen_time + timedelta(seconds=3600)

    @pytest.mark.parametrize("auth_token", [{"provider": MusicProvider.SPOTIFY}], indirect=["auth_token"])
    async def test__token_state__update(
        self,
        async_session_db: AsyncSession,
        frozen_time: datetime,
        user: User,
        token_state: OAuthProviderTokenState,
        auth_token: OAuthProviderUserToken,
        auth_token_repository: OAuthProviderTokenRepositoryPort,
        spotify_client: SpotifyOAuthClientAdapter,
        httpx_mock: HTTPXMock,
    ) -> None:
        httpx_mock.add_response(
            url=str(spotify_client.token_endpoint),
            method="POST",
            json={
                "token_type": token_state.token_type,
                "access_token": token_state.access_token,
                "refresh_token": token_state.refresh_token,
                "expires_in": 3600,
            },
        )

        await oauth_callback(
            code="foo",
            user=user,
            provider=MusicProvider.SPOTIFY,
            auth_token_repository=auth_token_repository,
            provider_client=spotify_client,
        )

        stmt_state = select(AuthProviderStateModel).where(
            AuthProviderStateModel.user_id == user.id,
            AuthProviderStateModel.provider == MusicProvider.SPOTIFY,
        )
        result_state = await async_session_db.execute(stmt_state)
        auth_state_db = result_state.scalar_one_or_none()
        assert auth_state_db is None

        stmt_token = select(AuthProviderTokenModel).where(
            AuthProviderTokenModel.user_id == user.id,
            AuthProviderTokenModel.provider == MusicProvider.SPOTIFY,
        )
        result_token = await async_session_db.execute(stmt_token)
        auth_token_db = result_token.scalar_one_or_none()

        assert auth_token_db is not None
        assert auth_token_db.token_type == token_state.token_type
        assert auth_token_db.token_access == token_state.access_token
        assert auth_token_db.token_refresh == token_state.refresh_token
        assert auth_token_db.token_expires_at == frozen_time + timedelta(seconds=3600)
