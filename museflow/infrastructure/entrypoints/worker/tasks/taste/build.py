import logging
from dataclasses import dataclass
from datetime import timedelta

from celery import Task

from museflow.application.inputs.taste import BuildTasteProfileConfigInput
from museflow.application.inputs.taste import BuildTasteProfileJobInput
from museflow.application.use_cases.taste_profile_build import BuildTasteProfileUseCase
from museflow.application.use_cases.user_get import get_user_by_id
from museflow.domain.entities.job import Job
from museflow.domain.enums import JobKind
from museflow.infrastructure.adapters.common.llm.usage import LLMUsageMeter
from museflow.infrastructure.adapters.progress.log import LogProgressAdapter
from museflow.infrastructure.config.settings.app import app_settings
from museflow.infrastructure.entrypoints.worker.const import JOB_TASK_NAMES
from museflow.infrastructure.entrypoints.worker.dependencies import get_wiring
from museflow.infrastructure.entrypoints.worker.jobs import run_job
from museflow.infrastructure.entrypoints.worker.main import celery_app

logger = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class TasteBuildJobResult:
    """What the job keeps of the profile built: the client reads the profile itself by its name."""

    name: str
    tracks_count: int


@celery_app.task(name=JOB_TASK_NAMES[JobKind.TASTE_BUILD], bind=True)
def taste_build_task(self: Task[[str, str], None], job_id: str, user_id: str) -> None:
    run_job(self, job_id, user_id, taste_build_work)


async def taste_build_work(job: Job) -> TasteBuildJobResult:
    """Builds the taste profile of the job, period by period, always resuming from its checkpoint.

    A second run (the message redelivered or retried) takes the lease its dead try left over and resumes after the
    last period saved, or returns the profile if that try finished it. A paused build fails the job: the same request
    queues another one, which resumes it.
    """
    wiring = get_wiring()
    uow = wiring.build_unit_of_work()
    job_in = BuildTasteProfileJobInput.model_validate(job.input)
    meter = LLMUsageMeter()

    # Accepted risk: a resumed build reads its periods again, which no longer match its checkpoint if the history
    # changed in between (an import), or if the job that paused it had another `rated_only`; the profile then mixes
    # both.
    config = BuildTasteProfileConfigInput(
        name=job_in.name,
        title=job_in.title,
        rated_only=job_in.rated_only,
        resume=True,
        throttling_sleep_seconds=app_settings.TASTE_PROFILE_BUILD_THROTTLING_SLEEP_SECONDS,
        lease_duration=timedelta(minutes=app_settings.TASTE_PROFILE_BUILD_LEASE_MINUTES),
        job_id=job.id,
    )

    try:
        async with wiring.build_profiler(meter=meter) as profiler:
            user = await get_user_by_id(job.user_id, uow=uow)
            use_case = BuildTasteProfileUseCase(uow=uow, profiler=profiler, progress=LogProgressAdapter())
            taste_profile = await use_case.build_profile(user=user, config=config)
    finally:
        # For the operator only: the client never sees an amount. A failed try was billed too.
        logger.info(
            f"Job {job.id}: LLM cost ${meter.total_cost:.4f}",
            extra={"job_id": str(job.id), "cost": float(meter.total_cost)},
        )

    return TasteBuildJobResult(name=taste_profile.name, tracks_count=taste_profile.tracks_count)
