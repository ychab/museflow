from collections.abc import Iterable
from unittest import mock

import pytest


@pytest.fixture
def mock_typer_prompt() -> Iterable[mock.Mock]:
    with mock.patch("typer.prompt") as patched:
        yield patched


@pytest.fixture
def mock_typer_confirm() -> Iterable[mock.Mock]:
    with mock.patch("typer.confirm") as patched:
        yield patched
