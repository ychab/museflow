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

from spotifagent.domain.ports.providers.client import ProviderOAuthClientPort
from spotifagent.domain.ports.repositories.auth import OAuthProviderStateRepositoryPort
from spotifagent.domain.ports.repositories.auth import OAuthProviderTokenRepositoryPort
from spotifagent.domain.ports.repositories.music import ArtistRepositoryPort
from spotifagent.domain.ports.repositories.music import TrackRepositoryPort
from spotifagent.domain.ports.repositories.users import UserRepositoryPort

type ContextPatcher = AbstractContextManager[mock.Mock]

type DatabasePatcherFactory = Callable[[str], ContextPatcher]
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
    with mock.patch("spotifagent.infrastructure.entrypoints.cli.main.configure_loggers") as patched:
        yield patched


@pytest.fixture
def runner(block_cli_configure_loggers: mock.Mock) -> CliRunner:
    return CliRunner()


@pytest.fixture
def target_path(request: pytest.FixtureRequest) -> str:
    if request.cls and hasattr(request.cls, "TARGET_PATH"):
        return request.cls.TARGET_PATH

    if hasattr(request.module, "TARGET_PATH"):
        return request.module.TARGET_PATH

    raise ValueError("Test class or module must define 'TARGET_PATH' to use auto-patching fixtures.")


# --- Patcher Factories ---


@pytest.fixture
def mock_get_db_factory() -> DatabasePatcherFactory:
    @contextmanager
    def _patcher(target_path: str) -> Iterator[mock.Mock]:
        session_mock = mock.Mock(name="db_session")

        @asynccontextmanager
        async def get_db() -> AsyncGenerator[mock.Mock]:
            yield session_mock

        with mock.patch(target_path, side_effect=get_db):
            yield session_mock

    return _patcher


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
        async def _mock_dependency() -> AsyncGenerator[Any]:
            yield dependency_instance

        with mock.patch(target_path, side_effect=_mock_dependency):
            yield dependency_instance

    return _patcher


# --- DB session Mock ---


@pytest.fixture
def mock_get_db(target_path: str, mock_get_db_factory: DatabasePatcherFactory) -> Iterable[mock.Mock]:
    with mock_get_db_factory(f"{target_path}.get_db") as mock_db:
        yield mock_db


# --- Repository Mocks ---


@pytest.fixture
def mock_user_repository(
    target_path: str,
    mock_dependency_factory: DependencyPatcherFactory,
) -> Iterable[mock.AsyncMock]:
    repo = mock.AsyncMock(spec=UserRepositoryPort)
    with mock_dependency_factory(f"{target_path}.get_user_repository", repo) as mock_repo:
        yield mock_repo


@pytest.fixture
def mock_auth_state_repository(
    target_path: str,
    mock_dependency_factory: DependencyPatcherFactory,
) -> Iterable[mock.AsyncMock]:
    repo = mock.AsyncMock(spec=OAuthProviderStateRepositoryPort)
    with mock_dependency_factory(f"{target_path}.get_auth_state_repository", repo) as mock_repo:
        yield mock_repo


@pytest.fixture
def mock_auth_token_repository(
    target_path: str,
    mock_dependency_factory: DependencyPatcherFactory,
) -> Iterable[mock.AsyncMock]:
    repo = mock.AsyncMock(spec=OAuthProviderTokenRepositoryPort)
    with mock_dependency_factory(f"{target_path}.get_auth_token_repository", repo) as mock_repo:
        yield mock_repo


@pytest.fixture
def mock_artist_repository(
    target_path: str,
    mock_dependency_factory: DependencyPatcherFactory,
) -> Iterable[mock.AsyncMock]:
    repo = mock.AsyncMock(spec=ArtistRepositoryPort)
    with mock_dependency_factory(f"{target_path}.get_artist_repository", repo) as mock_repo:
        yield mock_repo


@pytest.fixture
def mock_track_repository(
    target_path: str,
    mock_dependency_factory: DependencyPatcherFactory,
) -> Iterable[mock.AsyncMock]:
    repo = mock.AsyncMock(spec=TrackRepositoryPort)
    with mock_dependency_factory(f"{target_path}.get_track_repository", repo) as mock_repo:
        yield mock_repo


# --- Client Mocks ---


@pytest.fixture
def mock_spotify_client(
    target_path: str,
    mock_async_context_dependency_factory: AsyncDependencyPatcherFactory,
) -> Iterable[mock.Mock]:
    client = mock.Mock(spec=ProviderOAuthClientPort)
    with mock_async_context_dependency_factory(f"{target_path}.get_spotify_client", client) as mock_client:
        yield mock_client


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
