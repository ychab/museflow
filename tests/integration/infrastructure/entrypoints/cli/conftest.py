from collections.abc import Iterable
from collections.abc import Iterator
from contextlib import asynccontextmanager
from unittest import mock
from unittest.mock import patch

from sqlalchemy.ext.asyncio import AsyncSession

import pytest


@pytest.fixture(scope="function", autouse=True)
def patch_session_scope(async_session_db: AsyncSession) -> Iterator[None]:
    """Patches 'session_scope' in the CLI module to yield the test's transactional session."""

    @asynccontextmanager
    async def mock_scope():
        yield async_session_db

    target_path = "museflow.infrastructure.entrypoints.cli.dependencies.session_scope"
    with patch(target_path, side_effect=mock_scope):
        yield


@pytest.fixture
def mock_typer_prompt() -> Iterable[mock.Mock]:
    with mock.patch("typer.prompt") as patched:
        yield patched


@pytest.fixture
def mock_typer_confirm() -> Iterable[mock.Mock]:
    with mock.patch("typer.confirm") as patched:
        yield patched
