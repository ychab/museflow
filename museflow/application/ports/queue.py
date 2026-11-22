from abc import ABC
from abc import abstractmethod

from museflow.domain.entities.job import Job


class JobPublisherPort(ABC):
    """Port for the queue the workers take the jobs from."""

    @abstractmethod
    async def publish(self, job: Job) -> None:
        """Publishes the task message of the job, and waits until the broker has stored it.

        Raises:
            JobPublishError: If the broker is unreachable or refuses the message.
        """
        ...
