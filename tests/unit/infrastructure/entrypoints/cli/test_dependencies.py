from collections.abc import Iterator
from unittest import mock

from sqlalchemy.ext.asyncio import AsyncEngine

import pytest

from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.domain.entities.user import User
from museflow.domain.enums import MusicProvider
from museflow.domain.exceptions import ProviderAuthTokenNotFoundError
from museflow.infrastructure.adapters.database.unit_of_work import SQLUnitOfWork
from museflow.infrastructure.entrypoints.cli.dependencies import get_provider_library
from museflow.infrastructure.entrypoints.cli.dependencies import get_provider_oauth
from museflow.infrastructure.entrypoints.cli.dependencies import get_streaming_history_adapter
from museflow.infrastructure.entrypoints.cli.dependencies import get_unit_of_work
from museflow.infrastructure.entrypoints.cli.dependencies import run_with_database

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


class TestRunWithDatabase:
    @pytest.fixture
    def mock_engine(self) -> Iterator[mock.AsyncMock]:
        engine = mock.AsyncMock(spec=AsyncEngine)
        target_path = "museflow.infrastructure.entrypoints.cli.dependencies.create_engine_from_settings"
        with mock.patch(target_path, return_value=engine):
            yield engine

    def test__database_open_for_the_run_only(self, mock_engine: mock.AsyncMock) -> None:
        async def main() -> UnitOfWorkPort:
            return get_unit_of_work()

        assert isinstance(run_with_database(main()), SQLUnitOfWork)
        mock_engine.dispose.assert_awaited_once()

        with pytest.raises(RuntimeError, match="No database open"):
            get_unit_of_work()

    def test__error__disposes_engine(self, mock_engine: mock.AsyncMock) -> None:
        async def main() -> None:
            raise ValueError("boom")

        with pytest.raises(ValueError, match="boom"):
            run_with_database(main())

        mock_engine.dispose.assert_awaited_once()
