import dataclasses
import logging
from typing import Any

from celery import Task

from museflow.application.inputs.history import ImportStreamingHistoryConfigInput
from museflow.application.inputs.history import ImportStreamingHistoryJobInput
from museflow.application.ports.storage import FileStoragePort
from museflow.application.use_cases.track_history_import import ImportStreamingHistoryUseCase
from museflow.application.use_cases.user_get import get_user_by_id
from museflow.domain.entities.job import Job
from museflow.domain.enums import JobKind
from museflow.infrastructure.adapters.progress.log import LogProgressAdapter
from museflow.infrastructure.config.settings.app import app_settings
from museflow.infrastructure.entrypoints.worker.const import JOB_TASK_NAMES
from museflow.infrastructure.entrypoints.worker.const import TRANSIENT_ERRORS
from museflow.infrastructure.entrypoints.worker.dependencies import get_wiring
from museflow.infrastructure.entrypoints.worker.jobs import run_job
from museflow.infrastructure.entrypoints.worker.main import celery_app
from museflow.infrastructure.utils.archive import ArchiveLimits
from museflow.infrastructure.utils.archive import extract_files

logger = logging.getLogger(__name__)


@celery_app.task(name=JOB_TASK_NAMES[JobKind.TRACK_HISTORY_IMPORT], bind=True)
def track_history_import_task(self: Task[[str, str], None], job_id: str, user_id: str) -> None:
    run_job(self, job_id, user_id, track_history_import_work)


async def track_history_import_work(job: Job) -> dict[str, Any]:
    """Extracts the uploaded archive into the user's file storage, imports the files, then deletes them all.

    A second run (the message redelivered) does it again: the files extracted are written under the same keys, and
    the import creates no play twice.
    """
    wiring = get_wiring()
    uow = wiring.build_unit_of_work()
    file_storage = wiring.build_file_storage()
    job_in = ImportStreamingHistoryJobInput.model_validate(job.input)
    streaming_history = wiring.build_streaming_history(job_in.provider)

    use_case = ImportStreamingHistoryUseCase(
        uow=uow,
        streaming_history=streaming_history,
        file_storage=file_storage,
        progress=LogProgressAdapter(),
    )

    config = ImportStreamingHistoryConfigInput(
        prefix=job_in.files_prefix,
        min_ms_played=job_in.min_ms_played,
        purge=job_in.purge,
    )

    try:
        user = await get_user_by_id(job.user_id, uow=uow)
        await _extract_archive(job, job_in, pattern=streaming_history.file_pattern, file_storage=file_storage)
        report = await use_case.import_history(user=user, config=config)
    except TRANSIENT_ERRORS:
        # Kept for the next try. Accepted risk: after the last one, the job fails with its files left, until the
        # sweeper of #299 deletes them.
        raise
    except Exception:
        await file_storage.delete(user_id=job.user_id, prefix=job_in.prefix)
        raise

    await file_storage.delete(user_id=job.user_id, prefix=job_in.prefix)
    return dataclasses.asdict(report)


async def _extract_archive(
    job: Job,
    job_in: ImportStreamingHistoryJobInput,
    pattern: str,
    file_storage: FileStoragePort,
) -> None:
    archive = await file_storage.get(user_id=job.user_id, key=job_in.archive_key)

    limits = ArchiveLimits(
        max_file_size=app_settings.HISTORY_ARCHIVE_MAX_FILE_SIZE_MB * 1024 * 1024,
        max_extracted_size=app_settings.HISTORY_ARCHIVE_MAX_EXTRACTED_SIZE_MB * 1024 * 1024,
        max_entries=app_settings.HISTORY_ARCHIVE_MAX_ENTRIES,
    )

    # One file in memory at a time. Each under a folder of its rank in the archive: two files of the same name, from
    # two folders of the archive, are both kept (the import skips the plays saved twice).
    files_count = 0
    for archive_file in extract_files(archive, pattern=pattern, limits=limits):
        key = f"{job_in.files_prefix}/{archive_file.rank}/{archive_file.name}"
        await file_storage.put(user_id=job.user_id, key=key, content=archive_file.content)
        files_count += 1

    logger.info(
        f"Job {job.id}: archive extracted, {files_count} file(s)",
        extra={"job_id": str(job.id), "files_count": files_count},
    )
