import logging
from collections.abc import Iterable
from datetime import UTC
from datetime import datetime

import pytest
from time_machine import TimeMachineFixture


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
    from spotifagent.infrastructure.config.loggers import configure_loggers

    # Configure with test-friendly settings
    configure_loggers(level="DEBUG", handlers=["null"], propagate=True)

    yield

    logging.shutdown()


@pytest.fixture
def frozen_time(time_machine: TimeMachineFixture) -> datetime:
    fixed_dt = datetime(2026, 1, 1, tzinfo=UTC)
    time_machine.move_to(fixed_dt, tick=False)
    return fixed_dt
