from unittest import mock

import pytest

from museflow.application.use_cases.provider_oauth_callback import oauth_callback
from museflow.domain.entities.user import User
from museflow.domain.exceptions import ProviderExchangeCodeError
from museflow.domain.types import MusicProvider


class TestOauthCallbackUseCase:
    async def test__exchange_code__exception(
        self,
        user: User,
        mock_auth_token_repository: mock.AsyncMock,
        mock_provider_client: mock.Mock,
    ) -> None:
        mock_provider_client.exchange_code_for_token.side_effect = Exception("Boom")

        with pytest.raises(ProviderExchangeCodeError):
            await oauth_callback(
                code="foo",
                user=user,
                provider=MusicProvider.SPOTIFY,
                auth_token_repository=mock_auth_token_repository,
                provider_client=mock_provider_client,
            )
