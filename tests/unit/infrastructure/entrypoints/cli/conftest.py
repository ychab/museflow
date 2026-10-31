import re
from collections.abc import AsyncGenerator
from collections.abc import Callable
from collections.abc import Iterable
from collections.abc import Iterator
from contextlib import AbstractContextManager
from contextlib import asynccontextmanager
from contextlib import contextmanager
from typing import Any
from unittest import mock

import pytest
from typer.testing import CliRunner

from museflow.application.ports.enrichers.track import TrackEnricherPort
from museflow.application.ports.profilers.taste import TasteProfilerPort
from museflow.application.ports.providers.oauth import ProviderOAuthPort

type ContextPatcher = AbstractContextManager[mock.Mock]

type DependencyPatcherFactory = Callable[..., AbstractContextManager[mock.Mock]]
type AsyncDependencyPatcherFactory = Callable[..., AbstractContextManager[mock.Mock]]

type TextCleaner = Callable[[str], str]


@pytest.fixture(autouse=True)
def force_rich_terminal_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Force Rich/Typer to use a standard terminal width and no colors
    ONLY for CLI unit tests to ensure consistent output assertions.
    """
    monkeypatch.setenv("COLUMNS", "100")
    monkeypatch.setenv("TERM", "dumb")
    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.setenv("CI", "true")


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


# --- Patcher Factories ---


@pytest.fixture
def mock_dependency_factory() -> DependencyPatcherFactory:
    """Factory to patch standard CLI dependencies (Repositories, Services)."""

    @contextmanager
    def _patcher(target_path: str, return_value: Any) -> Iterator[mock.Mock]:
        with mock.patch(target_path, return_value=return_value) as _:
            yield return_value

    return _patcher


@pytest.fixture
def mock_async_context_dependency_factory() -> AsyncDependencyPatcherFactory:
    """Factory to patch async context manager CLI dependencies (SpotifyClient)."""

    @contextmanager
    def _patcher(target_path: str, dependency_instance: Any) -> Iterator[mock.Mock]:
        @asynccontextmanager
        async def _mock_dependency(*_: Any, **__: Any) -> AsyncGenerator[Any]:
            yield dependency_instance

        with mock.patch(target_path, side_effect=_mock_dependency):
            yield dependency_instance

    return _patcher


# --- Unit of work Mock ---


@pytest.fixture
def mock_get_unit_of_work(
    target_path: str,
    mock_dependency_factory: DependencyPatcherFactory,
    mock_uow: mock.AsyncMock,
) -> Iterable[mock.AsyncMock]:
    """Patches the command's `get_unit_of_work`; configure the repositories through the `mock_*_repository` fixtures."""
    with mock_dependency_factory(f"{target_path}.get_unit_of_work", mock_uow) as uow:
        yield uow


# --- Adapter Mocks ---


@pytest.fixture
def mock_spotify_client(
    target_path: str,
    mock_async_context_dependency_factory: AsyncDependencyPatcherFactory,
) -> Iterable[mock.AsyncMock]:
    client = mock.AsyncMock(spec=ProviderOAuthPort)
    with mock_async_context_dependency_factory(f"{target_path}.get_spotify_oauth", client) as mock_client:
        yield mock_client


@pytest.fixture
def mock_provider_oauth(
    target_path: str,
    mock_async_context_dependency_factory: AsyncDependencyPatcherFactory,
) -> Iterable[mock.AsyncMock]:
    client = mock.AsyncMock(spec=ProviderOAuthPort)
    with mock_async_context_dependency_factory(f"{target_path}.get_provider_oauth", client) as mock_client:
        yield mock_client


@pytest.fixture
def mock_provider_library_factory(
    target_path: str,
    mock_dependency_factory: DependencyPatcherFactory,
    mock_provider_library: mock.AsyncMock,
) -> Iterable[mock.Mock]:
    factory = mock.Mock()
    factory.create.return_value = mock_provider_library
    with mock_dependency_factory(f"{target_path}.get_provider_library_factory", factory):
        yield factory


@pytest.fixture
def mock_get_profiler(
    target_path: str,
    mock_async_context_dependency_factory: AsyncDependencyPatcherFactory,
) -> Iterable[mock.AsyncMock]:
    profiler = mock.AsyncMock(spec=TasteProfilerPort)
    with mock_async_context_dependency_factory(f"{target_path}.get_profiler", profiler) as mock_profiler:
        yield mock_profiler


@pytest.fixture
def mock_get_enricher(
    target_path: str,
    mock_async_context_dependency_factory: AsyncDependencyPatcherFactory,
) -> Iterable[mock.AsyncMock]:
    enricher = mock.AsyncMock(spec=TrackEnricherPort)
    with mock_async_context_dependency_factory(f"{target_path}.get_enricher", enricher) as mock_enricher:
        yield mock_enricher


# --- Helpers ---


@pytest.fixture
def clean_typer_text() -> TextCleaner:
    """
    Obviously, there is no easy way to disable all the rich text generated by
    Rich/Typer. We can try to set some environment variables like:
        NO_COLOR=1
        TERM=dumb
        Console_FORCE_TERMINAL=False
    Anyway, Typer still creates a rich.console.Console that defaults to a box style for errors...

    Then, the most pragmatic solution is to clean up the output without coupling
    our tests to specific terminal emulation settings.
    """

    def _cleaner(text: str) -> str:
        clean_text = re.sub(r"[│╭╰─]", "", text)
        return " ".join(clean_text.split())

    return _cleaner
