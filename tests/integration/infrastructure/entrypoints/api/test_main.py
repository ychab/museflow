from collections.abc import Iterator
from unittest import mock

from sqlalchemy.ext.asyncio import AsyncEngine

import pytest

from museflow.infrastructure.config.settings.app import app_settings
from museflow.infrastructure.entrypoints.api.main import app
from museflow.infrastructure.entrypoints.api.main import lifespan
from museflow.infrastructure.entrypoints.wiring import Wiring


@pytest.fixture
def mock_engine() -> Iterator[mock.AsyncMock]:
    engine = mock.AsyncMock(spec=AsyncEngine)
    with mock.patch("museflow.infrastructure.entrypoints.wiring.create_engine_from_settings", return_value=engine):
        yield engine


async def test__lifespan_configures_loggers(mock_api_logger: mock.Mock, mock_engine: mock.AsyncMock) -> None:
    async with lifespan(app):
        pass

    mock_api_logger.assert_called_once_with(
        level=app_settings.LOG_LEVEL_API,
        third_party_level=app_settings.LOG_LEVEL_THIRD_PARTY,
        handlers=app_settings.LOG_HANDLERS_API,
    )


async def test__lifespan_opens_the_wiring(mock_api_logger: mock.Mock, mock_engine: mock.AsyncMock) -> None:
    async with lifespan(app):
        assert isinstance(app.state.wiring, Wiring)
        assert app.state.wiring.session_factory.kw["bind"] is mock_engine
        mock_engine.dispose.assert_not_awaited()

    mock_engine.dispose.assert_awaited_once()
