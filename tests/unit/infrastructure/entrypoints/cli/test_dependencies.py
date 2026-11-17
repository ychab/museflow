from unittest import mock

import pytest

from museflow.domain.entities.user import User
from museflow.domain.enums import MusicProvider
from museflow.domain.exceptions import ProviderAuthTokenNotFoundError
from museflow.infrastructure.entrypoints.cli.dependencies import get_provider_library
from museflow.infrastructure.entrypoints.cli.dependencies import get_provider_oauth
from museflow.infrastructure.entrypoints.cli.dependencies import get_streaming_history_adapter

from tests.unit.factories.entities.auth import OAuthProviderUserTokenFactory


class TestDependencies:
    async def test__get_provider_oauth__unknown(self) -> None:
        with pytest.raises(ValueError, match="Unknown provider: FOO"):
            async with get_provider_oauth(provider="FOO"):  # type: ignore[arg-type]
                pass

    async def test__get_provider_library__auth_token_not_found(
        self,
        user: User,
        mock_uow: mock.AsyncMock,
        mock_auth_token_repository: mock.AsyncMock,
    ) -> None:
        mock_auth_token_repository.get.return_value = None

        with pytest.raises(
            ProviderAuthTokenNotFoundError, match="run 'museflow provider connect --provider spotify' first"
        ):
            async with get_provider_library(MusicProvider.SPOTIFY, user=user, uow=mock_uow):
                pass

    async def test__get_provider_library__unknown(
        self,
        user: User,
        mock_uow: mock.AsyncMock,
        mock_auth_token_repository: mock.AsyncMock,
    ) -> None:
        mock_auth_token_repository.get.return_value = OAuthProviderUserTokenFactory.build(user_id=user.id)

        with pytest.raises(ValueError, match="Unknown provider: FOO"):
            async with get_provider_library("FOO", user=user, uow=mock_uow):  # type: ignore[arg-type]
                pass

    def test__get_streaming_history_adapter__unknown(self) -> None:
        with pytest.raises(ValueError, match="Unknown provider: FOO"):
            get_streaming_history_adapter(provider="FOO")  # type: ignore[arg-type]
