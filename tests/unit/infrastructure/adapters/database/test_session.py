import importlib
from collections.abc import Iterator
from unittest import mock

from sqlalchemy.ext.asyncio import AsyncSession

import pytest

from museflow.infrastructure.adapters.database import session as session_module
from museflow.infrastructure.adapters.database.session import session_scope
from museflow.infrastructure.config.settings.database import database_settings


class TestSessionModule:
    @pytest.fixture
    def unset_database_uri(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(database_settings, "URI", None)

    @pytest.mark.usefixtures("unset_database_uri")
    def test__missing_database_uri(self) -> None:
        with pytest.raises(RuntimeError, match="DATABASE_ env vars"):
            importlib.reload(session_module)


class TestSessionScope:
    @pytest.fixture
    def mock_session(self) -> Iterator[mock.Mock]:
        session: mock.Mock = mock.Mock(
            spec=AsyncSession,
            rollback=mock.AsyncMock(),
            close=mock.AsyncMock(),
        )
        yield session
        session.reset_mock()

    @pytest.fixture
    def mock_session_factory(self, mock_session: mock.Mock) -> Iterator[mock.Mock]:
        with mock.patch("museflow.infrastructure.adapters.database.session.async_session_factory") as factory:
            factory.return_value = mock_session
            yield factory

    async def test__nominal(self, mock_session: mock.Mock, mock_session_factory: mock.Mock) -> None:
        async with session_scope() as session:
            assert session is mock_session

        mock_session_factory.assert_called_once()
        mock_session.close.assert_awaited_once()
        mock_session.rollback.assert_not_awaited()

    async def test_rollback_on_error(self, mock_session: mock.Mock, mock_session_factory: mock.Mock) -> None:
        with pytest.raises(ValueError, match="Database error"):
            async with session_scope():
                raise ValueError("Database error")

        mock_session_factory.assert_called_once()
        mock_session.rollback.assert_awaited_once()
        mock_session.close.assert_awaited_once()
