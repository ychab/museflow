from collections.abc import Iterable
from collections.abc import Iterator
from unittest import mock
from unittest.mock import patch

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import async_sessionmaker

import pytest


@pytest.fixture(scope="function", autouse=True)
def patch_session_factory(uow_session_factory: async_sessionmaker[AsyncSession]) -> Iterator[None]:
    """Points the CLI units of work at the test database, each block in a savepoint of the test transaction."""
    target_path = "museflow.infrastructure.entrypoints.cli.dependencies.async_session_factory"
    with patch(target_path, uow_session_factory):
        yield


@pytest.fixture
def mock_typer_prompt() -> Iterable[mock.Mock]:
    with mock.patch("typer.prompt") as patched:
        yield patched


@pytest.fixture
def mock_typer_confirm() -> Iterable[mock.Mock]:
    with mock.patch("typer.confirm") as patched:
        yield patched
