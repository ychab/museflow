import logging
import uuid

from museflow.application.ports.queue import JobPublisherPort
from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.domain.exceptions import JobPublishError

logger = logging.getLogger(__name__)


async def publish_jobs(limit: int, uow: UnitOfWorkPort, job_publisher: JobPublisherPort) -> int:
    """Publishes the task messages of the jobs not published yet, the oldest first, then marks them published.

    At least once: a crash between the publish and the mark publishes the job again next time, and the worker drops
    the duplicate. Stops at the first message the broker refuses, which stays for next time.

    Returns:
        How many jobs were published.
    """
    async with uow:
        jobs = await uow.jobs.get_unpublished(limit)

    # Out of any transaction: no connection waits on the broker
    published_ids: list[uuid.UUID] = []
    for job in jobs:
        try:
            await job_publisher.publish(job)
        except JobPublishError:
            logger.warning(f"Job {job.id} not published, retried next time", exc_info=True)
            break
        published_ids.append(job.id)

    if published_ids:
        async with uow:
            await uow.jobs.mark_published(published_ids)

    return len(published_ids)
