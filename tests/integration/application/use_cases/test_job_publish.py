from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kombu import Queue

from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.application.use_cases.job_publish import publish_jobs
from museflow.infrastructure.adapters.database.models import JobModel
from museflow.infrastructure.adapters.queue.celery import CeleryJobPublisher
from museflow.infrastructure.entrypoints.worker.const import JOB_TASK_NAMES
from museflow.infrastructure.entrypoints.worker.main import celery_app

from tests.integration.factories.models.job import JobModelFactory


class TestPublishJobsUseCase:
    async def test__nominal(self, async_session_db: AsyncSession, uow: UnitOfWorkPort, batch_queue: Queue) -> None:
        job_db = await JobModelFactory.create_async()

        published = await publish_jobs(
            10,
            uow=uow,
            job_publisher=CeleryJobPublisher(celery_app, task_names=JOB_TASK_NAMES),
        )

        assert published == 1
        message = batch_queue.get(no_ack=True)
        assert message is not None
        assert message.decode()[0] == [str(job_db.id), str(job_db.user_id)]
        published_at = await async_session_db.scalar(select(JobModel.published_at).where(JobModel.id == job_db.id))
        assert published_at is not None
