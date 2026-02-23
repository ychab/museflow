from datetime import datetime
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

import pytest
from pytest_httpx import HTTPXMock

from spotifagent.application.use_cases.oauth_callback import oauth_callback
from spotifagent.domain.entities.auth import OAuthProviderTokenState
from spotifagent.domain.entities.music import MusicProvider
from spotifagent.domain.entities.users import User
from spotifagent.domain.ports.repositories.spotify import SpotifyAccountRepositoryPort
from spotifagent.infrastructure.adapters.database.models import AuthProviderState as AuthProviderStateModel
from spotifagent.infrastructure.adapters.database.models import User as UserModel
from spotifagent.infrastructure.adapters.providers.spotify.client import SpotifyOAuthClientAdapter


class TestSpotifyOauthCallbackUseCase:
    async def test__token_state__create(
        self,
        async_session_db: AsyncSession,
        frozen_time: datetime,
        user: User,
        token_state: OAuthProviderTokenState,
        spotify_account_repository: SpotifyAccountRepositoryPort,
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
            spotify_account_repository=spotify_account_repository,
            provider_client=spotify_client,
        )

        stmt_auth = select(AuthProviderStateModel).where(
            AuthProviderStateModel.user_id == user.id,
            AuthProviderStateModel.provider == MusicProvider.SPOTIFY,
        )
        result_auth = await async_session_db.execute(stmt_auth)
        auth_state = result_auth.scalar_one_or_none()
        assert auth_state is None

        stmt_user = select(UserModel).where(UserModel.id == user.id).options(selectinload(UserModel.spotify_account))
        result_user = await async_session_db.execute(stmt_user)
        user_db = result_user.scalar_one()

        assert user_db.spotify_account is not None
        assert user_db.spotify_account.token_type == token_state.token_type
        assert user_db.spotify_account.token_access == token_state.access_token
        assert user_db.spotify_account.token_refresh == token_state.refresh_token
        assert user_db.spotify_account.token_expires_at == frozen_time + timedelta(seconds=3600)

    @pytest.mark.parametrize("user", [{"with_spotify_account": True}], indirect=["user"])
    async def test__token_state__update(
        self,
        async_session_db: AsyncSession,
        frozen_time: datetime,
        user: User,
        token_state: OAuthProviderTokenState,
        spotify_account_repository: SpotifyAccountRepositoryPort,
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
            spotify_account_repository=spotify_account_repository,
            provider_client=spotify_client,
        )

        stmt_auth = select(AuthProviderStateModel).where(
            AuthProviderStateModel.user_id == user.id,
            AuthProviderStateModel.provider == MusicProvider.SPOTIFY,
        )
        result_auth = await async_session_db.execute(stmt_auth)
        auth_state = result_auth.scalar_one_or_none()
        assert auth_state is None

        stmt_user = select(UserModel).where(UserModel.id == user.id).options(selectinload(UserModel.spotify_account))
        result_user = await async_session_db.execute(stmt_user)
        user_db = result_user.scalar_one()

        assert user_db.spotify_account is not None
        assert user_db.spotify_account.token_type == token_state.token_type
        assert user_db.spotify_account.token_access == token_state.access_token
        assert user_db.spotify_account.token_refresh == token_state.refresh_token
        assert user_db.spotify_account.token_expires_at == frozen_time + timedelta(seconds=3600)
