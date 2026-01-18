from unittest import mock

import pytest

from spotifagent.application.use_cases.spotify_oauth_callback import spotify_oauth_callback
from spotifagent.domain.entities.users import User
from spotifagent.domain.exceptions import SpotifyExchangeCodeError


class TestSpotifyOauthCallbackUseCase:
    async def test__exchange_code__exception(
        self,
        user: User,
        mock_user_repository: mock.AsyncMock,
        mock_spotify_account_repository: mock.AsyncMock,
        mock_spotify_client: mock.Mock,
    ) -> None:
        mock_spotify_client.exchange_code_for_token.side_effect = Exception("Boom")

        with pytest.raises(SpotifyExchangeCodeError):
            await spotify_oauth_callback(
                code="foo",
                user=user,
                user_repository=mock_user_repository,
                spotify_account_repository=mock_spotify_account_repository,
                spotify_client=mock_spotify_client,
            )
