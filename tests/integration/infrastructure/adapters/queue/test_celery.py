import uuid

import pytest
from celery import Celery
from kombu import Queue

from museflow.domain.entities.job import Job
from museflow.domain.enums import JobKind
from museflow.domain.exceptions import JobPublishError
from museflow.infrastructure.adapters.queue.celery import CeleryJobPublisher
from museflow.infrastructure.entrypoints.worker.const import JOB_TASK_NAMES
from museflow.infrastructure.entrypoints.worker.main import celery_app


class TestCeleryJobPublisher:
    @pytest.fixture
    def job(self) -> Job:
        return Job(user_id=uuid.uuid4(), kind=JobKind.TRACK_HISTORY_IMPORT)

    async def test__publish__nominal(self, job: Job, batch_queue: Queue) -> None:
        publisher = CeleryJobPublisher(celery_app, task_names=JOB_TASK_NAMES)

        await publisher.publish(job)

        # Routed by the task name, as a worker expects it: the IDs only, the job ID naming the task
        message = batch_queue.get(no_ack=True)
        assert message is not None
        assert message.headers["task"] == "track.history_import"
        assert message.headers["id"] == str(job.id)
        args, kwargs, _ = message.decode()
        assert args == [str(job.id), str(job.user_id)]
        assert kwargs == {}

    async def test__publish__broker_unreachable(self, job: Job) -> None:
        # Nothing listens on this port; no retry of the publish
        app = Celery(broker="amqp://museflow:museflow@127.0.0.1:1//")
        app.conf.update(task_publish_retry=False, broker_connection_timeout=1)
        publisher = CeleryJobPublisher(app, task_names=JOB_TASK_NAMES)

        with pytest.raises(JobPublishError):
            await publisher.publish(job)
