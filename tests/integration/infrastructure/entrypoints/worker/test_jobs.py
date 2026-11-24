from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

import anyio

from museflow.domain.enums import JobStatus
from museflow.infrastructure.adapters.database.models import JobModel

from tests.integration.factories.models.job import JobModelFactory
from tests.integration.infrastructure.entrypoints.worker.celery_worker import CeleryWorker
from tests.integration.infrastructure.entrypoints.worker.conftest import WAIT_TIMEOUT_SECONDS
from tests.integration.infrastructure.entrypoints.worker.conftest import JobWaiter
from tests.integration.infrastructure.entrypoints.worker.stub_tasks import job_once_killed_task
from tests.integration.infrastructure.entrypoints.worker.stub_tasks import job_task


class TestRunJob:
    async def test__nominal(
        self,
        worker: CeleryWorker,
        async_session_trans: AsyncSession,
        wait_for_job: JobWaiter,
    ) -> None:
        job_db = await self._create_job(async_session_trans)

        job_task.apply_async(args=(str(job_db.id), str(job_db.user_id)), task_id=str(job_db.id))

        job_db = await wait_for_job(job_db.id, JobStatus.DONE)
        assert job_db.result == {"user_id": str(job_db.user_id)}
        assert job_db.started_at is not None
        assert job_db.finished_at is not None

    async def test__error__failed(
        self,
        worker: CeleryWorker,
        async_session_trans: AsyncSession,
        wait_for_job: JobWaiter,
    ) -> None:
        job_db = await self._create_job(async_session_trans, input={"fail": True})

        job_task.apply_async(args=(str(job_db.id), str(job_db.user_id)), task_id=str(job_db.id))

        job_db = await wait_for_job(job_db.id, JobStatus.FAILED)
        assert job_db.error == "ValueError"

    async def test__running__duplicate__dropped(self, worker: CeleryWorker, async_session_trans: AsyncSession) -> None:
        # Running elsewhere: a fresh message for it is a duplicate of the relay's
        job_db = await self._create_job(async_session_trans, status=JobStatus.RUNNING)

        job_task.apply_async(args=(str(job_db.id), str(job_db.user_id)), task_id=str(job_db.id))

        with anyio.fail_after(WAIT_TIMEOUT_SECONDS):
            while f"Job {job_db.id} not started" not in worker.logs:
                await anyio.sleep(0.2)
        await async_session_trans.refresh(job_db)
        assert job_db.status == JobStatus.RUNNING
        assert job_db.result is None

    async def test__worker_killed__resumed(
        self,
        worker: CeleryWorker,
        broker_url: str,
        database_uri: str,
        file_storage_dir: Path,
        tmp_path: Path,
        async_session_trans: AsyncSession,
        wait_for_job: JobWaiter,
    ) -> None:
        started_file = tmp_path / "started"
        job_db = await self._create_job(async_session_trans, input={"started_file": str(started_file)})

        job_once_killed_task.apply_async(args=(str(job_db.id), str(job_db.user_id)), task_id=str(job_db.id))
        with anyio.fail_after(WAIT_TIMEOUT_SECONDS):
            while not (started_file.exists() and started_file.read_text()):
                await anyio.sleep(0.2)
        worker.kill()

        # The job is left running, and its message comes back redelivered: the next worker resumes it
        with CeleryWorker(
            broker_url=broker_url,
            database_uri=database_uri,
            file_storage_dir=file_storage_dir,
            log_file=tmp_path / "next.log",
        ):
            await wait_for_job(job_db.id, JobStatus.DONE)

    @staticmethod
    async def _create_job(session: AsyncSession, **kwargs: object) -> JobModel:
        job_db = await JobModelFactory.create_async(**kwargs)
        await session.commit()
        return job_db
