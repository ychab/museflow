import logging

from celery import Task

from museflow.application.inputs.enrich import EnrichTracksConfigInput
from museflow.application.inputs.enrich import EnrichTracksJobInput
from museflow.application.use_cases.track_enrich import EnrichTracksReport
from museflow.application.use_cases.track_enrich import EnrichTracksUseCase
from museflow.application.use_cases.user_get import get_user_by_id
from museflow.domain.entities.job import Job
from museflow.domain.enums import JobKind
from museflow.infrastructure.adapters.common.llm.usage import LLMUsageMeter
from museflow.infrastructure.adapters.progress.log import LogProgressAdapter
from museflow.infrastructure.entrypoints.worker.const import JOB_TASK_NAMES
from museflow.infrastructure.entrypoints.worker.dependencies import get_wiring
from museflow.infrastructure.entrypoints.worker.jobs import run_job
from museflow.infrastructure.entrypoints.worker.main import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name=JOB_TASK_NAMES[JobKind.TRACK_ENRICH], bind=True)
def track_enrich_task(task: Task[[str, str], None], job_id: str, user_id: str) -> None:
    run_job(task, job_id, user_id, track_enrich_work)


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
