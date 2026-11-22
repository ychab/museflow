from collections.abc import Iterator
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

import pytest

from tests.integration.infrastructure.entrypoints.worker.celery_worker import CeleryWorker


@pytest.fixture
def worker(
    broker_url: str,
    database_uri: str,
    tmp_path: Path,
    async_session_trans: AsyncSession,
) -> Iterator[CeleryWorker]:
    """A worker on the test database: its tasks commit, so the test reads with `async_session_trans`.

    Its logs print at the end, which pytest shows for a failed test only.
    """
    with CeleryWorker(broker_url=broker_url, database_uri=database_uri, log_file=tmp_path / "worker.log") as worker:
        yield worker

    print(worker.logs)
