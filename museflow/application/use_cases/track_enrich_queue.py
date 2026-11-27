import logging

from museflow.application.inputs.enrich import EnrichTracksJobInput
from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.domain.entities.job import Job
from museflow.domain.entities.user import User
from museflow.domain.enums import JobKind

logger = logging.getLogger(__name__)


async def queue_track_enrichment(user: User, job_in: EnrichTracksJobInput, uow: UnitOfWorkPort) -> Job:
    """Records the job that enriches the user's tracks, for a worker to run.

    The tracks are not read: a job with nothing to enrich is done at once, which costs a message and spares a second
    path that would race with the worker anyway.

    Raises:
        JobAlreadyActiveError: If an enrichment is already pending or running for the user.
    """
    async with uow:
        job = await uow.jobs.create(
            Job(
                user_id=user.id,
                kind=JobKind.TRACK_ENRICH,
                input=job_in.model_dump(mode="json"),
            )
        )

    logger.info(f"Enrichment queued: job {job.id}", extra={"job_id": str(job.id), "user_id": str(user.id)})
    return job
