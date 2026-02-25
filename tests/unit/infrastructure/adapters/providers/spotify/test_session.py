import asyncio
from datetime import datetime
from datetime import timedelta
from unittest import mock

import pytest

from museflow.domain.entities.auth import OAuthProviderTokenState
from museflow.domain.entities.auth import OAuthProviderUserToken
from museflow.domain.entities.users import User
from museflow.infrastructure.adapters.providers.spotify.exceptions import SpotifyTokenExpiredError
from museflow.infrastructure.adapters.providers.spotify.session import SpotifyOAuthSessionClient

from tests.unit.factories.auth import OAuthProviderTokenStateFactory
from tests.unit.factories.auth import OAuthProviderUserTokenFactory


class TestSpotifyOAuthSessionClient:
    """
    These unit tests are focus on concurrency control (locking, race conditions)
    and internal logic flow (Proactive vs Reactive triggers).
    """

    @pytest.fixture
    def session_client(
        self,
        user: User,
        auth_token: OAuthProviderUserToken,
        mock_auth_token_repository: mock.AsyncMock,
        mock_provider_client: mock.AsyncMock,
    ) -> SpotifyOAuthSessionClient:
        return SpotifyOAuthSessionClient(
            user=user,
            auth_token=auth_token,
            auth_token_repository=mock_auth_token_repository,
            client=mock_provider_client,
        )

    @pytest.fixture
    def auth_token_expired(
        self,
        frozen_time: datetime,
        session_client: SpotifyOAuthSessionClient,
    ) -> OAuthProviderUserToken:
        return OAuthProviderUserTokenFactory.build(
            token_expires_at=frozen_time - timedelta(seconds=session_client.token_buffer_seconds + 20),
        )

    async def test__execute__retry_fails_again(
        self,
        session_client: SpotifyOAuthSessionClient,
        mock_provider_client: mock.AsyncMock,
        token_state: OAuthProviderTokenState,
    ) -> None:
        mock_provider_client.make_user_api_call.side_effect = SpotifyTokenExpiredError()
        mock_provider_client.refresh_access_token.return_value = token_state

        with pytest.raises(SpotifyTokenExpiredError):
            await session_client.execute("GET", "/test")

        assert mock_provider_client.make_user_api_call.call_count == 2

    async def test__refresh_token_safely__reactive_skip(
        self,
        session_client: SpotifyOAuthSessionClient,
        mock_provider_client: mock.AsyncMock,
        mock_auth_token_repository: mock.AsyncMock,
        auth_token: OAuthProviderUserToken,
    ) -> None:
        session_client.auth_token = auth_token
        stale_token = "OLD_TOKEN_123"

        await session_client._refresh_token_safely(stale_access_token=stale_token)

        mock_provider_client.refresh_access_token.assert_not_called()
        mock_auth_token_repository.update.assert_not_called()

    async def test__concurrency__proactive_double_check_locking(
        self,
        session_client: SpotifyOAuthSessionClient,
        mock_provider_client: mock.AsyncMock,
        mock_auth_token_repository: mock.AsyncMock,
        auth_token_expired: OAuthProviderUserToken,
        token_state: OAuthProviderTokenState,
    ) -> None:
        session_client.auth_token = auth_token_expired

        async def slow_refresh(*args, **kwargs):
            await asyncio.sleep(0.05)
            return token_state

        mock_provider_client.refresh_access_token.side_effect = slow_refresh
        mock_provider_client.make_user_api_call.return_value = {}

        async with asyncio.TaskGroup() as tg:
            for _ in range(10):
                tg.create_task(session_client.execute("GET", "/test"))

        mock_provider_client.refresh_access_token.assert_called_once()
        mock_auth_token_repository.update.assert_called_once()

        assert mock_provider_client.make_user_api_call.call_count == 10
        for i, call in enumerate(mock_provider_client.make_user_api_call.call_args_list):
            assert call.kwargs["token_state"].access_token == token_state.access_token, i

    async def test__concurrency__reactive_refresh_locking(
        self,
        frozen_time: datetime,
        session_client: SpotifyOAuthSessionClient,
        mock_provider_client: mock.AsyncMock,
        mock_auth_token_repository: mock.AsyncMock,
        auth_token: OAuthProviderUserToken,
    ) -> None:
        """
        Test locking when multiple requests hit 401 simultaneously.
        """
        session_client.auth_token = auth_token
        new_token_state = OAuthProviderTokenStateFactory.build(
            expires_at=auth_token.token_expires_at + timedelta(seconds=3600)
        )

        async def slow_refresh(*args):
            await asyncio.sleep(0.05)
            return new_token_state

        mock_provider_client.refresh_access_token.side_effect = slow_refresh

        async def mock_api_call(token_state, **kwargs):
            # If using the NEW token -> Success
            if token_state.access_token == new_token_state.access_token:
                return {}

            # If using the OLD token (auth_token) -> 401
            raise SpotifyTokenExpiredError()

        mock_provider_client.make_user_api_call.side_effect = mock_api_call

        async with asyncio.TaskGroup() as tg:
            for _ in range(10):
                tg.create_task(session_client.execute("GET", "/test"))

        mock_provider_client.refresh_access_token.assert_called_once()
        assert mock_provider_client.make_user_api_call.call_count == 20  # 10 (initial failures) + 10 (retries)
