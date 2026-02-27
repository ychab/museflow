import logging
from collections.abc import Iterable
from datetime import UTC
from datetime import datetime

import pytest
from time_machine import TimeMachineFixture


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--slow",
        action="store_true",
        default=False,
        help="run slow tests",
    )
    parser.addoption(
        "--spotify-refresh-token",
        action="store",
        default=None,
        help="A valid Spotify Refresh Token to run live API tests.",
    )


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "slow: mark test as slow (not executed by default)")
    config.addinivalue_line("markers", "spotify_live: mark test as requiring live Spotify API access")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    # Create skip markers.
    skip_slow = pytest.mark.skip(reason="need --slow option to run")
    skip_spotify = pytest.mark.skip(reason="need --spotify-refresh-token option to run")

    # Automatically skip marked tests if the corresponding parse option is missing.
    for item in items:
        if item.get_closest_marker("slow") and not config.getoption("--slow"):
            item.add_marker(skip_slow)

        if item.get_closest_marker("spotify_live") and not config.getoption("--spotify-refresh-token"):
            item.add_marker(skip_spotify)


@pytest.fixture(scope="session", autouse=True)
def anyio_backend() -> str:
    """
    Configure anyio backend for all async tests.
    @see https://anyio.readthedocs.io/en/stable/testing.html#using-async-fixtures-with-higher-scopes
    """
    return "asyncio"


@pytest.fixture(scope="session", autouse=True)
def configure_logging() -> Iterable[None]:
    """Configure logging for ALL tests before anything else"""
    from museflow.infrastructure.config.loggers import configure_loggers

    # Configure with test-friendly settings
    configure_loggers(level="DEBUG", handlers=["null"], propagate=True)

    yield

    logging.shutdown()


@pytest.fixture
def frozen_time(time_machine: TimeMachineFixture) -> datetime:
    fixed_dt = datetime(2026, 1, 1, tzinfo=UTC)
    time_machine.move_to(fixed_dt, tick=False)
    return fixed_dt
