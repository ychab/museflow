from datetime import datetime
from datetime import timedelta
from unittest import mock

from fastapi import status
from httpx import AsyncClient

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

import pytest

from spotifagent.domain.entities.auth import OAuthProviderState
from spotifagent.domain.entities.music import MusicProvider
from spotifagent.domain.entities.spotify import SpotifyTokenState
from spotifagent.domain.entities.users import User
from spotifagent.domain.ports.repositories.auth import OAuthProviderStateRepositoryPort
from spotifagent.infrastructure.adapters.database.models import AuthProviderState as AuthProviderStateModel
from spotifagent.infrastructure.adapters.database.models import User as UserModel
from spotifagent.infrastructure.entrypoints.api.main import app


class TestSpotifyConnect:
    async def test_not_authenticated(self, async_client: AsyncClient) -> None:
        url = app.url_path_for("spotify_connect")
        response = await async_client.get(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_redirect(
        self,
        async_session_db: AsyncSession,
        auth_state_repository: OAuthProviderStateRepositoryPort,
        user: User,
        access_token: str,
        async_client: AsyncClient,
    ) -> None:
        auth_state = await auth_state_repository.get(user_id=user.id, provider=MusicProvider.SPOTIFY)
        assert auth_state is None

        url = app.url_path_for("spotify_connect")
        response = await async_client.get(url, follow_redirects=False)

        assert response.status_code == status.HTTP_307_TEMPORARY_REDIRECT
        assert response.headers["location"].startswith("https://")

        auth_state = await auth_state_repository.get(user_id=user.id, provider=MusicProvider.SPOTIFY)
        assert auth_state is not None


class TestSpotifyCallback:
    async def test__nominal__create_spotify_account(
        self,
        async_session_db: AsyncSession,
        frozen_time: datetime,
        user: User,
        auth_state: OAuthProviderState,
        mock_spotify_client: mock.AsyncMock,
        async_client: AsyncClient,
    ) -> None:
        assert user.spotify_account is None

        mock_spotify_client.exchange_code_for_token.return_value = SpotifyTokenState(
            token_type="Bearer",
            access_token="mock_access_token",
            refresh_token="mock_refresh_token",
            expires_at=frozen_time + timedelta(seconds=3600),
        )

        url = app.url_path_for("spotify_callback")
        response = await async_client.get(
            url,
            params={
                "code": "my_secret_code",
                "state": auth_state.state,
            },
        )
        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert response_data["message"] == "Spotify account linked successfully"

        stmt_auth = select(AuthProviderStateModel).where(
            AuthProviderStateModel.user_id == user.id,
            AuthProviderStateModel.provider == MusicProvider.SPOTIFY,
        )
        result_auth = await async_session_db.execute(stmt_auth)
        auth_state_db = result_auth.scalar_one_or_none()
        assert auth_state_db is None

        stmt = select(UserModel).where(UserModel.id == str(user.id)).options(selectinload(UserModel.spotify_account))
        result_user = await async_session_db.execute(stmt)
        user_db = result_user.scalar_one()
        assert user_db.spotify_account is not None
        assert user_db.spotify_account.token_type == "Bearer"
        assert user_db.spotify_account.token_access == "mock_access_token"
        assert user_db.spotify_account.token_refresh == "mock_refresh_token"
        assert user_db.spotify_account.token_expires_at == frozen_time + timedelta(seconds=3600)

    @pytest.mark.parametrize("user", [{"with_spotify_account": True}], indirect=["user"])
    async def test__nominal__update_spotify_account(
        self,
        async_session_db: AsyncSession,
        frozen_time: datetime,
        user: User,
        auth_state: OAuthProviderState,
        mock_spotify_client: mock.AsyncMock,
        async_client: AsyncClient,
    ) -> None:
        assert user.spotify_account is not None

        mock_spotify_client.exchange_code_for_token.return_value = SpotifyTokenState(
            token_type="Bearer",
            access_token="mock_access_token",
            refresh_token="mock_refresh_token",
            expires_at=frozen_time + timedelta(seconds=3600),
        )

        url = app.url_path_for("spotify_callback")
        response = await async_client.get(
            url,
            params={
                "code": "my_secret_code",
                "state": auth_state.state,
            },
        )
        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert response_data["message"] == "Spotify account linked successfully"

        stmt_auth = select(AuthProviderStateModel).where(
            AuthProviderStateModel.user_id == user.id,
            AuthProviderStateModel.provider == MusicProvider.SPOTIFY,
        )
        result_auth = await async_session_db.execute(stmt_auth)
        auth_state_db = result_auth.scalar_one_or_none()
        assert auth_state_db is None

        stmt = select(UserModel).where(UserModel.id == str(user.id)).options(selectinload(UserModel.spotify_account))
        result_user = await async_session_db.execute(stmt)
        user_db = result_user.scalar_one()
        assert user_db.spotify_account is not None
        assert user_db.spotify_account.token_type == "Bearer"
        assert user_db.spotify_account.token_access == "mock_access_token"
        assert user_db.spotify_account.token_refresh == "mock_refresh_token"
        assert user_db.spotify_account.token_expires_at == frozen_time + timedelta(seconds=3600)

    async def test__state__missing(self, async_client: AsyncClient) -> None:
        url = app.url_path_for("spotify_callback")
        response = await async_client.get(url, params={"state": ""})
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        response_data = response.json()
        assert response_data["detail"] == "Missing state parameter"

    async def test__state__invalid(self, async_client: AsyncClient) -> None:
        url = app.url_path_for("spotify_callback")
        response = await async_client.get(url, params={"state": "dummy"})
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        response_data = response.json()
        assert response_data["detail"] == "Invalid or expired state"

    async def test__spotify_error(self, auth_state: OAuthProviderState, async_client: AsyncClient) -> None:
        url = app.url_path_for("spotify_callback")
        response = await async_client.get(url, params={"state": auth_state.state, "error": "dummy error"})
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        response_data = response.json()
        assert response_data["detail"] == "OAuth error: dummy error"

    async def test__no_code(self, auth_state: OAuthProviderState, async_client: AsyncClient) -> None:
        url = app.url_path_for("spotify_callback")
        response = await async_client.get(url, params={"state": auth_state.state})
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        response_data = response.json()
        assert response_data["detail"] == "No authorization code received"

    async def test__exchange_code__exception(
        self,
        user: User,
        auth_state: OAuthProviderState,
        mock_spotify_client: mock.AsyncMock,
        async_client: AsyncClient,
    ) -> None:
        mock_spotify_client.exchange_code_for_token.side_effect = Exception("Boom")

        url = app.url_path_for("spotify_callback")
        response = await async_client.get(url, params={"state": auth_state.state, "code": "my_secret_code"})
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        response_data = response.json()
        assert response_data["detail"] == "Failed to exchange code"
