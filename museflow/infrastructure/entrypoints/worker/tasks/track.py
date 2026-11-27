import logging

from celery import Task

from museflow.application.inputs.enrich import EnrichTracksConfigInput
from museflow.application.inputs.enrich import EnrichTracksJobInput
from museflow.application.inputs.history import ImportStreamingHistoryConfigInput
from museflow.application.inputs.history import ImportStreamingHistoryJobInput
from museflow.application.use_cases.track_enrich import EnrichTracksReport
from museflow.application.use_cases.track_enrich import EnrichTracksUseCase
from museflow.application.use_cases.track_history_archive_extract import extract_history_archive
from museflow.application.use_cases.track_history_import import ImportStreamingHistoryReport
from museflow.application.use_cases.track_history_import import ImportStreamingHistoryUseCase
from museflow.application.use_cases.user_get import get_user_by_id
from museflow.domain.entities.job import Job
from museflow.domain.enums import JobKind
from museflow.infrastructure.adapters.common.llm.usage import LLMUsageMeter
from museflow.infrastructure.adapters.progress.log import LogProgressAdapter
from museflow.infrastructure.entrypoints.worker.const import JOB_TASK_NAMES
from museflow.infrastructure.entrypoints.worker.const import TRANSIENT_ERRORS
from museflow.infrastructure.entrypoints.worker.dependencies import get_wiring
from museflow.infrastructure.entrypoints.worker.jobs import run_job
from museflow.infrastructure.entrypoints.worker.main import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name=JOB_TASK_NAMES[JobKind.TRACK_HISTORY_IMPORT], bind=True)
def track_history_import_task(self: Task[[str, str], None], job_id: str, user_id: str) -> None:
    run_job(self, job_id, user_id, track_history_import_work)


async def track_history_import_work(job: Job) -> ImportStreamingHistoryReport:
    """Extracts the uploaded archive into the user's file storage, imports the files, then deletes them all.

    A second run (the message redelivered) does it again: the files extracted are written under the same keys, and
    the import creates no play twice.
    """
    wiring = get_wiring()
    uow = wiring.build_unit_of_work()
    file_storage = wiring.build_file_storage()
    archive_reader = wiring.build_archive_reader()
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
        archive = await file_storage.get(user_id=job.user_id, key=job_in.archive_key)

        files_count = await extract_history_archive(
            user=user,
            archive=archive,
            prefix=job_in.files_prefix,
            file_storage=file_storage,
            archive_reader=archive_reader,
            streaming_history=streaming_history,
        )
        logger.info(
            f"Job {job.id}: archive extracted, {files_count} file(s)",
            extra={"job_id": str(job.id), "files_count": files_count},
        )

        report = await use_case.import_history(user=user, config=config)
    except TRANSIENT_ERRORS:
        # Kept for the next try. Accepted risk: after the last one, the job fails with its files left, until the
        # sweeper of #299 deletes them.
        raise
    except Exception:
        await file_storage.delete(user_id=job.user_id, prefix=job_in.prefix)
        raise

    await file_storage.delete(user_id=job.user_id, prefix=job_in.prefix)
    return report


@celery_app.task(name=JOB_TASK_NAMES[JobKind.TRACK_ENRICH], bind=True)
def track_enrich_task(self: Task[[str, str], None], job_id: str, user_id: str) -> None:
    run_job(self, job_id, user_id, track_enrich_work)


async def track_enrich_work(job: Job) -> EnrichTracksReport:
    """Enriches the tracks missing a field of the job, batch by batch.

    A second run (the message redelivered or retried) resumes where the first stopped: each batch is saved once
    enriched, so its tracks no longer miss the field, and only the rest is paid.
    """
    wiring = get_wiring()
    uow = wiring.build_unit_of_work()
    job_in = EnrichTracksJobInput.model_validate(job.input)
    meter = LLMUsageMeter()

    try:
        async with wiring.build_enricher(meter=meter) as enricher:
            user = await get_user_by_id(job.user_id, uow=uow)
            use_case = EnrichTracksUseCase(uow=uow, track_enricher=enricher, progress=LogProgressAdapter())
            report = await use_case.enrich(user=user, config=EnrichTracksConfigInput(fields=job_in.fields))
    finally:
        # For the operator only: the client never sees an amount. A failed try was billed too.
        logger.info(
            f"Job {job.id}: LLM cost ${meter.total_cost:.4f}",
            extra={"job_id": str(job.id), "cost": float(meter.total_cost)},
        )

    return report
