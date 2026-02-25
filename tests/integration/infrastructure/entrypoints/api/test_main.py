from unittest import mock

from museflow.infrastructure.config.settings.app import app_settings
from museflow.infrastructure.entrypoints.api.main import app
from museflow.infrastructure.entrypoints.api.main import lifespan


async def test_lifespan_configures_loggers(mock_api_logger: mock.Mock) -> None:
    async with lifespan(app):
        pass

    mock_api_logger.assert_called_once_with(level=app_settings.LOG_LEVEL_API, handlers=app_settings.LOG_HANDLERS_API)
