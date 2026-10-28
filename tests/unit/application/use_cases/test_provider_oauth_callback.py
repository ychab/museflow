from unittest import mock

import pytest

from museflow.application.use_cases.provider_oauth_callback import oauth_callback
from museflow.domain.entities.user import User
from museflow.domain.enums import MusicProvider
from museflow.domain.exceptions import ProviderExchangeCodeError


class TestOauthCallbackUseCase:
    async def test__exchange_code__exception(
        self,
        mock_uow: mock.AsyncMock,
        user: User,
        mock_provider_oauth: mock.Mock,
    ) -> None:
        mock_provider_oauth.exchange_code_for_token.side_effect = Exception("Boom")

        with pytest.raises(ProviderExchangeCodeError):
            await oauth_callback(
                code="foo",
                user=user,
                provider=MusicProvider.SPOTIFY,
                uow=mock_uow,
                provider_oauth=mock_provider_oauth,
            )
