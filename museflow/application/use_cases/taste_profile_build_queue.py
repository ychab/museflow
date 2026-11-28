import logging

from museflow.application.inputs.taste import BuildTasteProfileJobInput
from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.domain.entities.job import Job
from museflow.domain.entities.user import User
from museflow.domain.enums import JobKind
from museflow.domain.enums import TasteProfileStatus
from museflow.domain.exceptions import TasteProfileAlreadyExistsError
from museflow.domain.exceptions import TasteProfileBuildInProgressError

logger = logging.getLogger(__name__)


async def queue_taste_profile_build(user: User, job_in: BuildTasteProfileJobInput, uow: UnitOfWorkPort) -> Job:
    """Records the job that builds the taste profile, for a worker to run.

    A profile still building (paused, or its job failed) is resumed from its checkpoint by the job.

    Raises:
        TasteProfileAlreadyExistsError: If a finished profile holds the name: delete it first to build it again.
        TasteProfileBuildInProgressError: If a build outside any job (the CLI) holds the profile. Not atomic: a build
            starting right after fails the job at its claim instead.
        JobAlreadyActiveError: If a build is already pending or running for the user, whatever its profile.
    """
    async with uow:
        taste_profile = await uow.taste_profiles.get(user_id=user.id, name=job_in.name)
        if taste_profile is not None and taste_profile.status == TasteProfileStatus.FINISHED:
            raise TasteProfileAlreadyExistsError(f"Taste profile '{job_in.name}' is already built: delete it first")

        if await uow.taste_builds.is_held(user_id=user.id, name=job_in.name):
            raise TasteProfileBuildInProgressError(
                f"A build of taste profile '{job_in.name}' is running: wait for it to end"
            )

        job = await uow.jobs.create(
            Job(
                user_id=user.id,
                kind=JobKind.TASTE_BUILD,
                input=job_in.model_dump(mode="json"),
            )
        )

    logger.info(
        f"Taste profile build queued: job {job.id}",
        extra={"job_id": str(job.id), "user_id": str(user.id)},
    )
    return job
