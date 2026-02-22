from unittest import mock

import pytest

from spotifagent.application.use_cases.oauth_callback import oauth_callback
from spotifagent.domain.entities.users import User
from spotifagent.domain.exceptions import ProviderExchangeCodeError


class TestSpotifyOauthCallbackUseCase:
    async def test__exchange_code__exception(
        self,
        user: User,
        mock_spotify_account_repository: mock.AsyncMock,
        mock_spotify_client: mock.Mock,
    ) -> None:
        mock_spotify_client.exchange_code_for_token.side_effect = Exception("Boom")

        with pytest.raises(ProviderExchangeCodeError):
            await oauth_callback(
                code="foo",
                user=user,
                spotify_account_repository=mock_spotify_account_repository,
                provider_client=mock_spotify_client,
            )
