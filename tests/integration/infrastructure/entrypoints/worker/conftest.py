import uuid
from collections.abc import Awaitable
from collections.abc import Callable
from collections.abc import Iterator
from pathlib import Path
from typing import Final

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import anyio
import pytest

from museflow.domain.enums import JobStatus
from museflow.infrastructure.adapters.database.models import JobModel

from tests.integration.infrastructure.entrypoints.worker.celery_worker import CeleryWorker

WAIT_TIMEOUT_SECONDS: Final[float] = 30.0

# Waits until a job reaches a status, then returns it
type JobWaiter = Callable[[uuid.UUID, JobStatus], Awaitable[JobModel]]


@pytest.fixture
def worker(
    broker_url: str,
    database_uri: str,
    file_storage_dir: Path,
    tmp_path: Path,
    async_session_trans: AsyncSession,
) -> Iterator[CeleryWorker]:
    """A worker on the test database: its tasks commit, so the test reads with `async_session_trans`.

    Its logs print at the end, which pytest shows for a failed test only.
    """
    with CeleryWorker(
        broker_url=broker_url,
        database_uri=database_uri,
        file_storage_dir=file_storage_dir,
        log_file=tmp_path / "worker.log",
    ) as worker:
        yield worker

    print(worker.logs)


@pytest.fixture
def wait_for_job(async_session_trans: AsyncSession) -> JobWaiter:
    """Polls the job a worker runs, as a client would, until it reaches the status."""

    async def wait(job_id: uuid.UUID, status: JobStatus) -> JobModel:
        with anyio.fail_after(WAIT_TIMEOUT_SECONDS):
            while True:
                async_session_trans.expire_all()
                statement = select(JobModel).where(JobModel.id == job_id)
                job_db = (await async_session_trans.execute(statement)).scalar_one()
                if job_db.status == status:
                    return job_db
                await anyio.sleep(0.2)

    return wait
