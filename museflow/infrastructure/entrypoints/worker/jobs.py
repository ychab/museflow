import logging
import uuid
from collections.abc import Callable
from collections.abc import Coroutine
from typing import Any

from celery import Task

from museflow.application.use_cases.job_run import RunJobUseCase
from museflow.domain.entities.job import Job
from museflow.infrastructure.entrypoints.worker.const import TRANSIENT_ERRORS
from museflow.infrastructure.entrypoints.worker.dependencies import get_wiring
from museflow.infrastructure.entrypoints.worker.dependencies import run_task

logger = logging.getLogger(__name__)

# What a job task runs once its job started: the use case of its kind, returning the result of the job
type JobWork = Callable[[Job], Coroutine[Any, Any, dict[str, Any] | None]]


def run_job(task: Task, job_id: str, user_id: str, work: JobWork) -> None:  # type: ignore[type-arg]
    """Runs the work of a job task between the start of its job and its end, done or failed.

    Call it from a bound task (`bind=True`), with the IDs its message carries. A message for a job already running
    resumes it only when it comes back after its attempt died: redelivered (the worker died) or retried (its process
    died). Any other is a duplicate of the relay's, dropped.
    """
    request = task.request
    resumed = bool(request.delivery_info and request.delivery_info.get("redelivered")) or request.retries > 0
    # A transient error is retried until this one, then fails the job as any other error
    last_try = request.retries >= (task.max_retries or 0)

    run_task(_run_job(uuid.UUID(job_id), uuid.UUID(user_id), work, resumed=resumed, last_try=last_try))


async def _run_job(job_id: uuid.UUID, user_id: uuid.UUID, work: JobWork, resumed: bool, last_try: bool) -> None:
    use_case = RunJobUseCase(user_id=user_id, job_id=job_id, uow=get_wiring().build_unit_of_work())

    job = await use_case.start(resumed=resumed)
    if job is None:
        return

    try:
        result = await work(job)
    except Exception as e:
        if isinstance(e, TRANSIENT_ERRORS) and not last_try:
            raise

        # The name of the error only: the client may show it, never its message, which may hold internals.
        # Accepted risk: if this write fails too (the database unreachable), or if the process dies on every try (no
        # code left to run it), the job stays running for good, its kind blocked, until the operator fails it by hand.
        await use_case.fail(type(e).__name__)
        # Celery logs the traceback of the error raised again
        logger.warning(f"Job {job_id} failed: {type(e).__name__}", extra={"job_id": str(job_id)})
        raise

    await use_case.finish(result)
    logger.info(f"Job {job_id} done", extra={"job_id": str(job_id)})
