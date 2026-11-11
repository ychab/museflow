import os
from collections.abc import Iterable
from collections.abc import Iterator
from unittest import mock
from unittest.mock import patch

from pydantic import HttpUrl

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import async_sessionmaker

import pytest
from tenacity import stop_after_attempt

from museflow.infrastructure.adapters.common.llm.client import OpenRouterClient
from museflow.infrastructure.config.settings.openrouter import openrouter_settings


@pytest.fixture(scope="function", autouse=True)
def patch_session_factory(uow_session_factory: async_sessionmaker[AsyncSession]) -> Iterator[None]:
    """Points the CLI units of work at the test database, each block in a savepoint of the test transaction."""
    target_path = "museflow.infrastructure.entrypoints.cli.dependencies.async_session_factory"
    with patch(target_path, uow_session_factory):
        yield


@pytest.fixture
def openrouter_settings_wiremock(monkeypatch: pytest.MonkeyPatch) -> None:
    """Points the OpenRouter client built by the CLI dependencies at WireMock, which serves a self-signed certificate."""
    monkeypatch.setattr(openrouter_settings, "BASE_URL", HttpUrl(os.environ["WIREMOCK_OPENROUTER_BASE_URL"]))
    monkeypatch.setattr(openrouter_settings, "VERIFY_SSL", False)
    monkeypatch.setattr(OpenRouterClient.make_api_call.retry, "stop", stop_after_attempt(1))


@pytest.fixture
def mock_typer_prompt() -> Iterable[mock.Mock]:
    with mock.patch("typer.prompt") as patched:
        yield patched


@pytest.fixture
def mock_typer_confirm() -> Iterable[mock.Mock]:
    with mock.patch("typer.confirm") as patched:
        yield patched
