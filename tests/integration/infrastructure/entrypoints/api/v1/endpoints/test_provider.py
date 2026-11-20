from datetime import UTC
from datetime import datetime
from datetime import timedelta
from typing import Final
from urllib.parse import parse_qs
from urllib.parse import urlsplit

from fastapi import status
from httpx import AsyncClient

import pytest
from time_machine import TimeMachineFixture

from museflow.application.ports.repositories.auth import OAuthProviderStateRepository
from museflow.application.ports.repositories.auth import OAuthProviderTokenRepository
from museflow.domain.const import OAUTH_STATE_TTL_SECONDS
from museflow.domain.entities.auth import OAuthProviderState
from museflow.domain.entities.auth import OAuthProviderUserToken
from museflow.domain.entities.user import User
from museflow.domain.enums import MusicProvider
from museflow.infrastructure.adapters.providers.spotify.oauth import SpotifyOAuthAdapter
from museflow.infrastructure.entrypoints.api.main import app

from tests.integration.factories.models.auth import AuthProviderStateModelFactory
from tests.integration.factories.models.user import UserModelFactory
from tests.integration.utils.wiremock import WireMockContext

# Both allowed by the test settings (pyproject.toml): a web client's page, a mobile app's scheme.
WEB_REDIRECT_URI: Final[str] = "https://app.example.com/spotify/callback"
MOBILE_REDIRECT_URI: Final[str] = "museflow://spotify/callback"


class TestProviderConnect:
    async def test__not_authenticated(self, async_client: AsyncClient) -> None:
        url = app.url_path_for("provider_connect", provider=MusicProvider.SPOTIFY)
        response = await async_client.post(url, params={"redirect_uri": WEB_REDIRECT_URI})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.parametrize("redirect_uri", [WEB_REDIRECT_URI, MOBILE_REDIRECT_URI])
    async def test__nominal(
        self,
        auth_state_repository: OAuthProviderStateRepository,
        user: User,
        access_token: str,
        async_client: AsyncClient,
        redirect_uri: str,
    ) -> None:
        url = app.url_path_for("provider_connect", provider=MusicProvider.SPOTIFY)
        response = await async_client.post(url, params={"redirect_uri": redirect_uri})
        assert response.status_code == status.HTTP_200_OK

        auth_state = await auth_state_repository.get(user_id=user.id, provider=MusicProvider.SPOTIFY)
        assert auth_state is not None

        # The provider sends the browser back to the client, never to the API.
        query = parse_qs(urlsplit(response.json()["authorization_url"]).query)
        assert query["redirect_uri"] == [redirect_uri]
        assert query["state"] == [auth_state.state]

    @pytest.mark.parametrize(
        "redirect_uri",
        [
            pytest.param("https://attacker.example.com/spotify/callback", id="other_host"),
            pytest.param("https://app.example.com/spotify/callback/other", id="other_path"),
        ],
    )
    async def test__redirect_uri__not_allowed(
        self,
        auth_state_repository: OAuthProviderStateRepository,
        user: User,
        access_token: str,
        async_client: AsyncClient,
        redirect_uri: str,
    ) -> None:
        url = app.url_path_for("provider_connect", provider=MusicProvider.SPOTIFY)
        response = await async_client.post(url, params={"redirect_uri": redirect_uri})
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()["detail"] == "Redirect URI not allowed"

        assert await auth_state_repository.get(user_id=user.id, provider=MusicProvider.SPOTIFY) is None

    async def test__redirect_uri__missing(self, access_token: str, async_client: AsyncClient) -> None:
        url = app.url_path_for("provider_connect", provider=MusicProvider.SPOTIFY)
        response = await async_client.post(url)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test__provider__unknown(self, access_token: str, async_client: AsyncClient) -> None:
        url = app.url_path_for("provider_connect", provider="foo")
        response = await async_client.post(url, params={"redirect_uri": WEB_REDIRECT_URI})
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


@pytest.mark.wiremock("spotify")
class TestProviderConnectComplete:
    @pytest.fixture
    def token_endpoint_ok(self, spotify_oauth: SpotifyOAuthAdapter, spotify_wiremock: WireMockContext) -> None:
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

    async def test__not_authenticated(self, auth_state: OAuthProviderState, async_client: AsyncClient) -> None:
        url = app.url_path_for("provider_connect_complete", provider=MusicProvider.SPOTIFY)
        response = await async_client.post(
            url,
            params={"redirect_uri": WEB_REDIRECT_URI},
            json={"code": "my_secret_code", "state": auth_state.state},
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.usefixtures("token_endpoint_ok")
    async def test__nominal__create_auth_token(
        self,
        frozen_time: datetime,
        user: User,
        auth_state: OAuthProviderState,
        auth_state_repository: OAuthProviderStateRepository,
        auth_token_repository: OAuthProviderTokenRepository,
        access_token: str,
        spotify_oauth: SpotifyOAuthAdapter,
        async_client: AsyncClient,
    ) -> None:
        url = app.url_path_for("provider_connect_complete", provider=MusicProvider.SPOTIFY)
        response = await async_client.post(
            url,
            params={"redirect_uri": WEB_REDIRECT_URI},
            json={"code": "my_secret_code", "state": auth_state.state},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["message"] == "Spotify account linked successfully"

        assert await auth_state_repository.get(user_id=user.id, provider=MusicProvider.SPOTIFY) is None

        auth_token = await auth_token_repository.get(user_id=user.id, provider=MusicProvider.SPOTIFY)
        assert auth_token is not None
        assert auth_token.token_type == "Bearer"
        assert auth_token.token_access == "dummy-access-token"
        assert auth_token.token_refresh == "dummy-refresh-token"
        assert auth_token.token_expires_at == frozen_time + timedelta(seconds=3600)

    @pytest.mark.usefixtures("token_endpoint_ok")
    @pytest.mark.parametrize("auth_token", [{"provider": MusicProvider.SPOTIFY}], indirect=["auth_token"])
    async def test__nominal__update_auth_token(
        self,
        user: User,
        auth_state: OAuthProviderState,
        auth_token: OAuthProviderUserToken,
        auth_token_repository: OAuthProviderTokenRepository,
        access_token: str,
        spotify_oauth: SpotifyOAuthAdapter,
        async_client: AsyncClient,
    ) -> None:
        url = app.url_path_for("provider_connect_complete", provider=MusicProvider.SPOTIFY)
        response = await async_client.post(
            url,
            params={"redirect_uri": WEB_REDIRECT_URI},
            json={"code": "my_secret_code", "state": auth_state.state},
        )
        assert response.status_code == status.HTTP_200_OK

        updated_token = await auth_token_repository.get(user_id=user.id, provider=MusicProvider.SPOTIFY)
        assert updated_token is not None
        assert updated_token.id == auth_token.id
        assert updated_token.token_access == "dummy-access-token"
        assert updated_token.token_refresh == "dummy-refresh-token"

    @pytest.mark.usefixtures("token_endpoint_ok")
    async def test__state__other_user(
        self,
        user: User,
        auth_state_repository: OAuthProviderStateRepository,
        auth_token_repository: OAuthProviderTokenRepository,
        access_token: str,
        spotify_oauth: SpotifyOAuthAdapter,
        async_client: AsyncClient,
    ) -> None:
        # #101: someone starts a flow, consents with their own provider account, then gets this user to send the code
        # and the state. Without the check, that person's provider account would be linked to this user.
        other_user_db = await UserModelFactory.create_async()
        other_state_db = await AuthProviderStateModelFactory.create_async(
            user_id=other_user_db.id,
            provider=MusicProvider.SPOTIFY,
        )

        url = app.url_path_for("provider_connect_complete", provider=MusicProvider.SPOTIFY)
        response = await async_client.post(
            url,
            params={"redirect_uri": WEB_REDIRECT_URI},
            json={"code": "my_secret_code", "state": other_state_db.state},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()["detail"] == "Invalid or expired state"

        assert await auth_token_repository.get(user_id=user.id, provider=MusicProvider.SPOTIFY) is None
        assert await auth_token_repository.get(user_id=other_user_db.id, provider=MusicProvider.SPOTIFY) is None
        # Single use: the state of the other flow is spent too.
        assert await auth_state_repository.get(user_id=other_user_db.id, provider=MusicProvider.SPOTIFY) is None

    async def test__state__invalid(self, access_token: str, async_client: AsyncClient) -> None:
        url = app.url_path_for("provider_connect_complete", provider=MusicProvider.SPOTIFY)
        response = await async_client.post(
            url,
            params={"redirect_uri": WEB_REDIRECT_URI},
            json={"code": "my_secret_code", "state": "dummy"},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()["detail"] == "Invalid or expired state"

    async def test__state__expired(
        self,
        user: User,
        auth_state: OAuthProviderState,
        auth_state_repository: OAuthProviderStateRepository,
        access_token: str,
        time_machine: TimeMachineFixture,
        async_client: AsyncClient,
    ) -> None:
        time_machine.move_to(datetime.now(UTC) + timedelta(seconds=OAUTH_STATE_TTL_SECONDS), tick=False)

        url = app.url_path_for("provider_connect_complete", provider=MusicProvider.SPOTIFY)
        response = await async_client.post(
            url,
            params={"redirect_uri": WEB_REDIRECT_URI},
            json={"code": "my_secret_code", "state": auth_state.state},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()["detail"] == "Invalid or expired state"

        assert await auth_state_repository.get(user_id=user.id, provider=MusicProvider.SPOTIFY) is None

    async def test__redirect_uri__not_allowed(
        self,
        user: User,
        auth_state: OAuthProviderState,
        auth_state_repository: OAuthProviderStateRepository,
        access_token: str,
        async_client: AsyncClient,
    ) -> None:
        url = app.url_path_for("provider_connect_complete", provider=MusicProvider.SPOTIFY)
        response = await async_client.post(
            url,
            params={"redirect_uri": "https://attacker.example.com/spotify/callback"},
            json={"code": "my_secret_code", "state": auth_state.state},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()["detail"] == "Redirect URI not allowed"

        # Refused before the state is read: the flow can still end with the right redirect URI.
        assert await auth_state_repository.get(user_id=user.id, provider=MusicProvider.SPOTIFY) is not None

    async def test__payload__invalid(self, access_token: str, async_client: AsyncClient) -> None:
        url = app.url_path_for("provider_connect_complete", provider=MusicProvider.SPOTIFY)
        response = await async_client.post(url, params={"redirect_uri": WEB_REDIRECT_URI}, json={"state": "dummy"})
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test__provider__unknown(self, access_token: str, async_client: AsyncClient) -> None:
        url = app.url_path_for("provider_connect_complete", provider="foo")
        response = await async_client.post(
            url,
            params={"redirect_uri": WEB_REDIRECT_URI},
            json={"code": "my_secret_code", "state": "dummy"},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test__exchange_code__exception(
        self,
        user: User,
        auth_state: OAuthProviderState,
        auth_state_repository: OAuthProviderStateRepository,
        auth_token_repository: OAuthProviderTokenRepository,
        access_token: str,
        spotify_oauth: SpotifyOAuthAdapter,
        async_client: AsyncClient,
        spotify_wiremock: WireMockContext,
    ) -> None:
        spotify_wiremock.create_mapping(
            method="POST",
            url_path=spotify_oauth.token_endpoint.path or "",
            status=500,
        )

        url = app.url_path_for("provider_connect_complete", provider=MusicProvider.SPOTIFY)
        response = await async_client.post(
            url,
            params={"redirect_uri": WEB_REDIRECT_URI},
            json={"code": "my_secret_code", "state": auth_state.state},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()["detail"] == "Failed to exchange code"

        # Single use: a new flow needs a new `connect`.
        assert await auth_state_repository.get(user_id=user.id, provider=MusicProvider.SPOTIFY) is None
        assert await auth_token_repository.get(user_id=user.id, provider=MusicProvider.SPOTIFY) is None
