from datetime import UTC
from datetime import datetime
from datetime import timedelta

from fastapi import status
from httpx import AsyncClient

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import pytest
from time_machine import TimeMachineFixture

from museflow.application.ports.repositories.auth import OAuthProviderStateRepository
from museflow.application.ports.repositories.auth import OAuthProviderTokenRepository
from museflow.domain.const import OAUTH_STATE_TTL_SECONDS
from museflow.domain.entities.auth import OAuthProviderState
from museflow.domain.entities.auth import OAuthProviderUserToken
from museflow.domain.entities.user import User
from museflow.domain.enums import MusicProvider
from museflow.infrastructure.adapters.database.models import AuthProviderState as AuthProviderStateModel
from museflow.infrastructure.adapters.database.models import AuthProviderToken as AuthProviderTokenModel
from museflow.infrastructure.adapters.providers.spotify.oauth import SpotifyOAuthAdapter
from museflow.infrastructure.config.settings.spotify import spotify_settings
from museflow.infrastructure.entrypoints.api.main import app

from tests.integration.utils.wiremock import WireMockContext


class TestProviderConnect:
    async def test__not_authenticated(self, async_client: AsyncClient) -> None:
        url = app.url_path_for("provider_connect", provider=MusicProvider.SPOTIFY)
        response = await async_client.get(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test__redirect(
        self,
        async_session_db: AsyncSession,
        auth_state_repository: OAuthProviderStateRepository,
        user: User,
        access_token: str,
        async_client: AsyncClient,
    ) -> None:
        auth_state = await auth_state_repository.get(user_id=user.id, provider=MusicProvider.SPOTIFY)
        assert auth_state is None

        url = app.url_path_for("provider_connect", provider=MusicProvider.SPOTIFY)
        response = await async_client.get(url, follow_redirects=False)

        assert response.status_code == status.HTTP_307_TEMPORARY_REDIRECT
        assert response.headers["location"].startswith("https://")

        auth_state = await auth_state_repository.get(user_id=user.id, provider=MusicProvider.SPOTIFY)
        assert auth_state is not None

    async def test__provider__unknown(self, access_token: str, async_client: AsyncClient) -> None:
        url = app.url_path_for("provider_connect", provider="foo")
        response = await async_client.get(url, follow_redirects=False)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


@pytest.mark.wiremock("spotify")
class TestProviderCallback:
    def test__url__matches_spotify_redirect_uri(self) -> None:
        # This URL is registered in the Spotify dashboard.
        url = app.url_path_for("provider_callback", provider=MusicProvider.SPOTIFY)
        assert url == spotify_settings.REDIRECT_URI.path

    async def test__provider__unknown(self, auth_state: OAuthProviderState, async_client: AsyncClient) -> None:
        url = app.url_path_for("provider_callback", provider="foo")
        response = await async_client.get(url, params={"state": auth_state.state, "code": "my_secret_code"})
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test__nominal__create_auth_token(
        self,
        async_session_db: AsyncSession,
        frozen_time: datetime,
        user: User,
        auth_state: OAuthProviderState,
        spotify_oauth: SpotifyOAuthAdapter,
        async_client: AsyncClient,
        spotify_wiremock: WireMockContext,
    ) -> None:
        spotify_wiremock.create_mapping(
            method="POST",
            url_path=spotify_oauth.token_endpoint.path or "",
            status=200,
            json_body={
                "token_type": "Bearer",
                "access_token": "dummy-access-token",
                "refresh_token": "dummy-refresh-token",
                "expires_in": 3600,
            },
        )

        url = app.url_path_for("provider_callback", provider=MusicProvider.SPOTIFY)
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
        assert auth_token_db.token_type == "Bearer"
        assert auth_token_db.token_access == "dummy-access-token"
        assert auth_token_db.token_refresh == "dummy-refresh-token"
        assert auth_token_db.token_expires_at == frozen_time + timedelta(seconds=3600)

    @pytest.mark.parametrize("auth_token", [{"provider": MusicProvider.SPOTIFY}], indirect=["auth_token"])
    async def test__nominal__update_auth_token(
        self,
        async_session_db: AsyncSession,
        frozen_time: datetime,
        user: User,
        auth_state: OAuthProviderState,
        auth_token: OAuthProviderUserToken,
        spotify_oauth: SpotifyOAuthAdapter,
        async_client: AsyncClient,
        spotify_wiremock: WireMockContext,
    ) -> None:
        spotify_wiremock.create_mapping(
            method="POST",
            url_path=spotify_oauth.token_endpoint.path or "",
            status=200,
            json_body={
                "token_type": "Bearer",
                "access_token": "dummy-access-token",
                "refresh_token": "dummy-refresh-token",
                "expires_in": 3600,
            },
        )

        url = app.url_path_for("provider_callback", provider=MusicProvider.SPOTIFY)
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
        assert auth_token_db.token_type == "Bearer"
        assert auth_token_db.token_access == "dummy-access-token"
        assert auth_token_db.token_refresh == "dummy-refresh-token"
        assert auth_token_db.token_expires_at == frozen_time + timedelta(seconds=3600)

    async def test__state__missing(self, async_client: AsyncClient) -> None:
        url = app.url_path_for("provider_callback", provider=MusicProvider.SPOTIFY)
        response = await async_client.get(url, params={"state": ""})
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        response_data = response.json()
        assert response_data["detail"] == "Missing state parameter"

    async def test__state__invalid(self, async_client: AsyncClient) -> None:
        url = app.url_path_for("provider_callback", provider=MusicProvider.SPOTIFY)
        response = await async_client.get(url, params={"state": "dummy"})
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        response_data = response.json()
        assert response_data["detail"] == "Invalid or expired state"

    async def test__state__expired(
        self,
        user: User,
        auth_state: OAuthProviderState,
        auth_state_repository: OAuthProviderStateRepository,
        time_machine: TimeMachineFixture,
        async_client: AsyncClient,
    ) -> None:
        time_machine.move_to(datetime.now(UTC) + timedelta(seconds=OAUTH_STATE_TTL_SECONDS), tick=False)

        url = app.url_path_for("provider_callback", provider=MusicProvider.SPOTIFY)
        response = await async_client.get(url, params={"state": auth_state.state, "code": "my_secret_code"})
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        response_data = response.json()
        assert response_data["detail"] == "Invalid or expired state"
        assert await auth_state_repository.get(user_id=user.id, provider=MusicProvider.SPOTIFY) is None

    @pytest.mark.parametrize("user", [{"is_active": False}], indirect=True)
    async def test__user__inactive(
        self,
        async_session_db: AsyncSession,
        user: User,
        auth_state: OAuthProviderState,
        async_client: AsyncClient,
    ) -> None:
        url = app.url_path_for("provider_callback", provider=MusicProvider.SPOTIFY)
        response = await async_client.get(url, params={"state": auth_state.state, "code": "my_secret_code"})
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "User account is inactive" in response.json()["detail"]

        stmt = select(AuthProviderTokenModel).where(AuthProviderTokenModel.user_id == user.id)
        result = await async_session_db.execute(stmt)
        assert result.scalar_one_or_none() is None

    async def test__provider_error(
        self,
        user: User,
        auth_state: OAuthProviderState,
        auth_state_repository: OAuthProviderStateRepository,
        auth_token_repository: OAuthProviderTokenRepository,
        async_client: AsyncClient,
    ) -> None:
        url = app.url_path_for("provider_callback", provider=MusicProvider.SPOTIFY)
        response = await async_client.get(url, params={"state": auth_state.state, "error": "dummy error"})
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        response_data = response.json()
        assert response_data["detail"] == "OAuth authorisation failed"

        # `provider connect` relies on this: the state is gone, only the token tells the flow failed.
        assert await auth_state_repository.get(user_id=user.id, provider=MusicProvider.SPOTIFY) is None
        assert await auth_token_repository.get(user_id=user.id, provider=MusicProvider.SPOTIFY) is None

    async def test__no_code(self, auth_state: OAuthProviderState, async_client: AsyncClient) -> None:
        url = app.url_path_for("provider_callback", provider=MusicProvider.SPOTIFY)
        response = await async_client.get(url, params={"state": auth_state.state})
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        response_data = response.json()
        assert response_data["detail"] == "No authorization code received"

    async def test__exchange_code__exception(
        self,
        user: User,
        auth_state: OAuthProviderState,
        auth_state_repository: OAuthProviderStateRepository,
        auth_token_repository: OAuthProviderTokenRepository,
        spotify_oauth: SpotifyOAuthAdapter,
        async_client: AsyncClient,
        spotify_wiremock: WireMockContext,
    ) -> None:
        spotify_wiremock.create_mapping(
            method="POST",
            url_path=spotify_oauth.token_endpoint.path or "",
            status=500,
        )

        url = app.url_path_for("provider_callback", provider=MusicProvider.SPOTIFY)
        response = await async_client.get(url, params={"state": auth_state.state, "code": "my_secret_code"})
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        response_data = response.json()
        assert response_data["detail"] == "Failed to exchange code"

        # `provider connect` relies on this: the state is gone, only the token tells the flow failed.
        assert await auth_state_repository.get(user_id=user.id, provider=MusicProvider.SPOTIFY) is None
        assert await auth_token_repository.get(user_id=user.id, provider=MusicProvider.SPOTIFY) is None
