import re
from collections.abc import Callable
from collections.abc import Iterable
from datetime import timedelta
from decimal import Decimal
from unittest import mock

import pytest
from typer.testing import CliRunner

from museflow.application.ports.enrichers.track import TrackEnricherPort
from museflow.application.ports.profilers.taste import TasteProfilerPort
from museflow.application.ports.providers.oauth import ProviderOAuthPort
from museflow.domain.enums import ReasoningEffort
from museflow.infrastructure.adapters.common.llm.schemas import ChatUsage
from museflow.infrastructure.adapters.common.llm.usage import LLMUsageMeter
from museflow.infrastructure.entrypoints.wiring import Wiring

type TextCleaner = Callable[[str], str]


def spend(meter: LLMUsageMeter) -> None:
    """Records one paid reply, as the OpenRouter client does: the CLI tests mock the logic that would call it."""
    meter.record(
        "advisor",
        "google/gemini-2.5-flash",
        ReasoningEffort.LOW,
        ChatUsage(prompt_tokens=1000, cost=Decimal("0.0123")),
        timedelta(seconds=2),
    )


@pytest.fixture(autouse=True)
def force_rich_terminal_width(monkeypatch: pytest.MonkeyPatch) -> None:
    """Gives Rich/Typer a fixed width, so that the output wraps the same way everywhere.

    No colour to turn off here: `TTY_COMPATIBLE=0`, in the pytest env, already keeps every console out of a terminal.
    """
    monkeypatch.setenv("COLUMNS", "100")


@pytest.fixture
def block_cli_configure_loggers() -> Iterable[mock.Mock]:
    """Prevent the CLI 'main' callback from re-configuring logging during tests."""
    with mock.patch("museflow.infrastructure.entrypoints.cli.main.configure_loggers") as patched:
        yield patched


@pytest.fixture
def runner(block_cli_configure_loggers: mock.Mock) -> CliRunner:
    return CliRunner()


@pytest.fixture
def target_path(request: pytest.FixtureRequest) -> str:
    if request.cls and hasattr(request.cls, "TARGET_PATH"):
        return str(request.cls.TARGET_PATH)

    if hasattr(request.module, "TARGET_PATH"):
        return str(request.module.TARGET_PATH)

    raise ValueError("Test class or module must define 'TARGET_PATH' to use auto-patching fixtures.")


# --- Typer mocks ---


@pytest.fixture
def mock_typer_prompt() -> Iterable[mock.Mock]:
    with mock.patch("typer.prompt") as patched:
        yield patched


@pytest.fixture
def mock_typer_confirm() -> Iterable[mock.Mock]:
    with mock.patch("typer.confirm") as patched:
        yield patched


# --- Wiring Mocks ---


@pytest.fixture
def mock_wiring(target_path: str, mock_uow: mock.AsyncMock) -> Iterable[mock.MagicMock]:
    """Patches the command's `get_wiring`.

    Configure the repositories through the `mock_*_repository` fixtures, the adapters through the `mock_build_*` ones.
    A `build_*` left alone returns a `MagicMock`, an async context manager too.
    """
    wiring = mock.MagicMock(spec=Wiring)
    wiring.build_unit_of_work.return_value = mock_uow

    with mock.patch(f"{target_path}.get_wiring", return_value=wiring):
        yield wiring


@pytest.fixture
def mock_provider_oauth(mock_wiring: mock.MagicMock) -> mock.AsyncMock:
    client = mock.AsyncMock(spec=ProviderOAuthPort)
    mock_wiring.build_provider_oauth.return_value.__aenter__.return_value = client
    return client


@pytest.fixture
def mock_build_provider_library(mock_wiring: mock.MagicMock, mock_provider_library: mock.AsyncMock) -> mock.MagicMock:
    mock_wiring.build_provider_library.return_value.__aenter__.return_value = mock_provider_library
    builder: mock.MagicMock = mock_wiring.build_provider_library
    return builder


@pytest.fixture
def mock_build_profiler(mock_wiring: mock.MagicMock) -> mock.MagicMock:
    profiler = mock.AsyncMock(spec=TasteProfilerPort, usages=[])
    mock_wiring.build_profiler.return_value.__aenter__.return_value = profiler
    builder: mock.MagicMock = mock_wiring.build_profiler
    return builder


@pytest.fixture
def mock_build_enricher(mock_wiring: mock.MagicMock) -> mock.MagicMock:
    enricher = mock.AsyncMock(spec=TrackEnricherPort, usages=[])
    mock_wiring.build_enricher.return_value.__aenter__.return_value = enricher
    builder: mock.MagicMock = mock_wiring.build_enricher
    return builder


# --- Helpers ---


@pytest.fixture
def clean_typer_text() -> TextCleaner:
    """Removes the box borders of Typer's error panels and joins the wrapped lines.

    Without colours (`TTY_COMPATIBLE=0`), Rich still draws the boxes and wraps the text at the width: the assertions
    then look for a message whatever its layout.
    """

    def _cleaner(text: str) -> str:
        clean_text = re.sub(r"[│╭╰─]", "", text)
        return " ".join(clean_text.split())

    return _cleaner
