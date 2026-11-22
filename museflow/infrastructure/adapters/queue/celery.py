import asyncio
from collections.abc import Mapping
from typing import Any

from celery import Celery
from kombu.exceptions import KombuError

from museflow.application.ports.queue import JobPublisherPort
from museflow.domain.entities.job import Job
from museflow.domain.enums import JobKind
from museflow.domain.exceptions import JobPublishError


class CeleryJobPublisher(JobPublisherPort):
    """Publishes the task of a job through the Celery app of the workers, so that it takes their routes and queues.

    The app must confirm its publishes (`confirm_publish`): a publish then returns once RabbitMQ has stored the message.
    """

    # Any task class: the app's own is the worker's
    def __init__(self, app: Celery[Any], task_names: Mapping[JobKind, str]) -> None:
        self._app = app
        self._task_names = task_names

    async def publish(self, job: Job) -> None:
        # The message carries IDs only: the task reloads what it needs. The job ID names the task too, which ties the
        # worker's logs to the job.
        try:
            await asyncio.to_thread(
                self._app.send_task,
                self._task_names[job.kind],
                args=[str(job.id), str(job.user_id)],
                task_id=str(job.id),
            )
        except (KombuError, OSError) as e:
            raise JobPublishError(f"Job {job.id} not published: {e}") from e
