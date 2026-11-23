import uuid
from abc import ABC
from abc import abstractmethod
from typing import Any

from museflow.domain.entities.job import Job


class JobRepository(ABC):
    """Port for the background jobs: the source of truth of their status, and the outbox of their task messages.

    A job is created unpublished; the relay publishes its message, then marks it published, in another transaction.
    """

    @abstractmethod
    async def create(self, job: Job) -> Job:
        """Records a pending job, and wakes the relay up once the transaction commits.

        Raises:
            JobAlreadyActiveError: If a job of the same kind is already pending or running for the user.
        """
        ...

    @abstractmethod
    async def get(self, user_id: uuid.UUID, job_id: uuid.UUID) -> Job | None: ...

    @abstractmethod
    async def get_list(self, user_id: uuid.UUID, limit: int | None = None, offset: int = 0) -> list[Job]:
        """Return the user's jobs, the newest first. `limit` and `offset` page them; no limit returns them all."""
        ...

    @abstractmethod
    async def count(self, user_id: uuid.UUID) -> int:
        """Return how many jobs `get_list` finds, all pages together."""
        ...

    @abstractmethod
    async def get_unpublished(self, limit: int) -> list[Job]:
        """Return the jobs whose task message was never published, of every user, the oldest first."""
        ...

    @abstractmethod
    async def mark_published(self, job_ids: list[uuid.UUID]) -> None: ...

    @abstractmethod
    async def start(self, user_id: uuid.UUID, job_id: uuid.UUID, resumed: bool) -> Job | None:
        """Moves the job to running, in one compare-and-set: of two workers starting it at once, one only wins.

        A pending job starts. A running one starts again only if `resumed`: its message comes back because the attempt
        running it died, so no one works on it any more; otherwise the message is a duplicate, and its job runs
        elsewhere.

        Returns:
            The running job, or None if the worker must not run it (unknown, finished, or running elsewhere).
        """
        ...

    @abstractmethod
    async def finish(self, user_id: uuid.UUID, job_id: uuid.UUID, result: dict[str, Any] | None) -> bool:
        """Moves a running job to done, with its result.

        Returns:
            False if the job was no longer running: ended elsewhere, nothing changed.
        """
        ...

    @abstractmethod
    async def fail(self, user_id: uuid.UUID, job_id: uuid.UUID, error: str) -> bool:
        """Moves a running job to failed, with its error.

        Returns:
            False if the job was no longer running: ended elsewhere, nothing changed.
        """
        ...
