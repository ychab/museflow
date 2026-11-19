import os
from collections.abc import Iterable
from collections.abc import Iterator
from unittest import mock
from unittest.mock import patch

from pydantic import HttpUrl

import pytest
from tenacity import stop_after_attempt

from museflow.infrastructure.adapters.common.llm.client import OpenRouterClient
from museflow.infrastructure.config.settings.openrouter import openrouter_settings
from museflow.infrastructure.entrypoints.wiring import Wiring


@pytest.fixture(scope="function", autouse=True)
def patch_wiring(wiring: Wiring) -> Iterator[None]:
    """Points the CLI wiring at the test database, each unit of work block in a savepoint of the test transaction."""
    with patch("museflow.infrastructure.entrypoints.cli.dependencies.wiring", wiring):
        yield


@pytest.fixture
def openrouter_settings_wiremock(monkeypatch: pytest.MonkeyPatch) -> None:
    """Points the OpenRouter client built by the wiring at WireMock, which serves a self-signed certificate."""
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
