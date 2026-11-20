from collections.abc import Iterable
from typing import Final
from unittest import mock
from urllib.parse import parse_qs
from urllib.parse import urlsplit

import pytest

from museflow.application.ports.repositories.auth import OAuthProviderStateRepository
from museflow.domain.entities.user import User
from museflow.domain.enums import MusicProvider
from museflow.infrastructure.config.settings.app import app_settings
from museflow.infrastructure.entrypoints.cli.commands.provider.connect import provider_connect_complete_logic
from museflow.infrastructure.entrypoints.cli.commands.provider.connect import provider_connect_start_logic

TARGET_PATH: Final[str] = "museflow.infrastructure.entrypoints.cli.commands.provider.connect"


class TestProviderConnectLogic:
    @pytest.fixture
    def mock_exchange_oauth_code(self) -> Iterable[mock.AsyncMock]:
        with mock.patch(f"{TARGET_PATH}.exchange_oauth_code", new_callable=mock.AsyncMock) as patched:
            yield patched

    async def test__nominal(
        self,
        user: User,
        auth_state_repository: OAuthProviderStateRepository,
        mock_exchange_oauth_code: mock.AsyncMock,
    ) -> None:
        start = await provider_connect_start_logic(user.email, MusicProvider.SPOTIFY)

        auth_state = await auth_state_repository.get(user_id=user.id, provider=MusicProvider.SPOTIFY)
        assert auth_state is not None

        # The provider sends the browser back to the loopback address, not to the API.
        query = parse_qs(urlsplit(start.authorization_url).query)
        assert query["redirect_uri"] == [str(app_settings.cli_oauth_redirect_uri)]
        assert query["state"] == [auth_state.state]

        # The URL the user pastes, with the spaces of a sloppy copy.
        redirect_url = f" {app_settings.cli_oauth_redirect_uri}?code=my_secret_code&state={auth_state.state}\n"
        await provider_connect_complete_logic(start, redirect_url)

        assert await auth_state_repository.get(user_id=user.id, provider=MusicProvider.SPOTIFY) is None
        mock_exchange_oauth_code.assert_awaited_once_with(
            code="my_secret_code",
            user=user,
            provider=MusicProvider.SPOTIFY,
            uow=mock.ANY,
            provider_oauth=mock.ANY,
        )
