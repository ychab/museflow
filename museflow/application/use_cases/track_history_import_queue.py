import logging
import uuid

from museflow.application.inputs.history import ImportStreamingHistoryJobInput
from museflow.application.ports.storage import FileStoragePort
from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.domain.entities.job import Job
from museflow.domain.entities.user import User
from museflow.domain.enums import JobKind
from museflow.domain.enums import MusicProvider

logger = logging.getLogger(__name__)


async def queue_history_import(
    user: User,
    archive: bytes,
    provider: MusicProvider,
    min_ms_played: int,
    purge: bool,
    uow: UnitOfWorkPort,
    file_storage: FileStoragePort,
) -> Job:
    """Stores the streaming history export, as is, then records the job that imports it, for a worker to run.

    The archive is stored first: a job never points to a file that is not there yet.

    Raises:
        JobAlreadyActiveError: If a history import is already pending or running for the user. The archive is deleted.
    """
    job_id = uuid.uuid4()
    job_in = ImportStreamingHistoryJobInput(
        prefix=f"history/{job_id}",
        provider=provider,
        min_ms_played=min_ms_played,
        purge=purge,
    )

    await file_storage.put(user_id=user.id, key=job_in.archive_key, content=archive)

    # Accepted risk: a process dying before the commit leaves the archive without a job, until the sweeper of #299
    # deletes it.
    try:
        async with uow:
            job = await uow.jobs.create(
                Job(
                    id=job_id,
                    user_id=user.id,
                    kind=JobKind.TRACK_HISTORY_IMPORT,
                    input=job_in.model_dump(mode="json"),
                )
            )
    except Exception:
        await file_storage.delete(user_id=user.id, prefix=job_in.prefix)
        raise

    logger.info(f"History import queued: job {job.id}", extra={"job_id": str(job.id), "user_id": str(user.id)})
    return job
