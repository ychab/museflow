from unittest import mock

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import async_sessionmaker

import pytest

from museflow.domain.entities.user import User
from museflow.domain.enums import MusicProvider
from museflow.domain.exceptions import ProviderAuthTokenNotFoundError
from museflow.infrastructure.entrypoints.wiring import Wiring

from tests.unit.factories.entities.auth import OAuthProviderUserTokenFactory


@pytest.fixture
def wiring() -> Wiring:
    return Wiring(mock.Mock(spec=async_sessionmaker[AsyncSession]))


class TestBuildProviderOAuth:
    async def test__unknown(self, wiring: Wiring) -> None:
        with pytest.raises(ValueError, match="Unknown provider: FOO"):
            async with wiring.build_provider_oauth(provider="FOO"):  # type: ignore[arg-type]
                pass


class TestBuildProviderLibrary:
    async def test__auth_token_not_found(
        self,
        wiring: Wiring,
        user: User,
        mock_uow: mock.AsyncMock,
        mock_auth_token_repository: mock.AsyncMock,
    ) -> None:
        mock_auth_token_repository.get.return_value = None

        with pytest.raises(ProviderAuthTokenNotFoundError, match="No spotify auth token found"):
            async with wiring.build_provider_library(MusicProvider.SPOTIFY, user=user, uow=mock_uow):
                pass

    async def test__unknown(
        self,
        wiring: Wiring,
        user: User,
        mock_uow: mock.AsyncMock,
        mock_auth_token_repository: mock.AsyncMock,
    ) -> None:
        mock_auth_token_repository.get.return_value = OAuthProviderUserTokenFactory.build(user_id=user.id)

        with pytest.raises(ValueError, match="Unknown provider: FOO"):
            async with wiring.build_provider_library("FOO", user=user, uow=mock_uow):  # type: ignore[arg-type]
                pass


class TestBuildStreamingHistory:
    def test__unknown(self, wiring: Wiring) -> None:
        with pytest.raises(ValueError, match="Unknown provider: FOO"):
            wiring.build_streaming_history(provider="FOO")  # type: ignore[arg-type]
