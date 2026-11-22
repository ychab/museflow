import logging
import uuid
from typing import Any

from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.domain.entities.job import Job

logger = logging.getLogger(__name__)


class RunJobUseCase:
    """The life of a job in a worker: started, then finished with its result or failed with its error.

    The task runs the use case of its kind between `start` and `finish`, each step in its own transaction: the work
    commits its own checkpoints, and a worker dying in between leaves the job running, for its redelivered message to
    resume.
    """

    def __init__(self, user_id: uuid.UUID, job_id: uuid.UUID, uow: UnitOfWorkPort) -> None:
        self._user_id = user_id
        self._job_id = job_id
        self._uow = uow

    async def start(self, resumed: bool) -> Job | None:
        """Moves the job to running.

        Args:
            resumed: The message comes back after the attempt running the job died (redelivered, or retried).

        Returns:
            The running job, or None if the task must not run it: unknown, finished, or running elsewhere (a
            duplicate message).
        """
        async with self._uow as uow:
            job = await uow.jobs.start(self._user_id, self._job_id, resumed=resumed)

        if job is None:
            logger.info(f"Job {self._job_id} not started: unknown, finished or running elsewhere")
        return job

    async def finish(self, result: dict[str, Any] | None) -> None:
        async with self._uow as uow:
            await uow.jobs.finish(self._user_id, self._job_id, result)

    async def fail(self, error: str) -> None:
        async with self._uow as uow:
            await uow.jobs.fail(self._user_id, self._job_id, error)
