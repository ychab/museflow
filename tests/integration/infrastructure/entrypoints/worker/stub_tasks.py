import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from celery import Task

from museflow.application.inputs.user import UserCreateInput
from museflow.application.use_cases.user_create import create_user
from museflow.domain.entities.job import Job
from museflow.infrastructure.entrypoints.worker.dependencies import get_wiring
from museflow.infrastructure.entrypoints.worker.dependencies import run_task
from museflow.infrastructure.entrypoints.worker.jobs import run_job
from museflow.infrastructure.entrypoints.worker.main import celery_app

# Stub tasks that prove the Celery setup itself (retries, dead letters, a lost worker, routing), apart from the real
# tasks, which are tested on what they do. Loaded by the test workers only (`celery worker --include`). Each one runs a
# use case against the database, as a real task does: the test sees it ran from the user it created.

PASSWORD: Final[str] = "a-test-password"


@dataclass(frozen=True, kw_only=True)
class _StubReport:
    user_id: str


@celery_app.task(name="tests.create_user")
def create_user_task(email: str) -> None:
    run_task(_create_user(email))


# Named as a playlist task, so that their route takes it
@celery_app.task(name="playlist.tests_create_user")
def create_user_as_playlist_task(email: str) -> None:
    run_task(_create_user(email))


@celery_app.task(name="tests.create_user_after_transient_error", bind=True)
def create_user_after_transient_error_task(task: Task[[str], None], email: str) -> None:
    if task.request.retries == 0:
        raise ConnectionError("The database is unreachable")

    run_task(_create_user(email))


@celery_app.task(name="tests.fail")
def fail_task(email: str) -> None:
    raise ValueError(f"Not worth a retry: {email}")


@celery_app.task(name="tests.create_user_once_killed")
def create_user_once_killed_task(email: str, started_file: str) -> None:
    """On its first run, writes its process ID to `started_file` and waits for the test to kill it; then creates the
    user."""
    started = Path(started_file)

    # Runs in the process the test kills, which never saves its coverage
    if not started.exists():  # pragma: no cover
        started.write_text(str(os.getpid()))
        time.sleep(60)

    run_task(_create_user(email))


@celery_app.task(name="tests.job", bind=True)
def job_task(task: Task[[str, str], None], job_id: str, user_id: str) -> None:
    """A job task, as a real one: its work returns the job's result, or fails it when the job's input says so."""
    run_job(task, job_id, user_id, _work)


@celery_app.task(name="tests.job_once_killed", bind=True)
def job_once_killed_task(task: Task[[str, str], None], job_id: str, user_id: str) -> None:
    """A job task whose first run writes its process ID to the `started_file` of the job's input, then waits for the
    test to kill it."""
    run_job(task, job_id, user_id, _work_once_killed)


async def _work(job: Job) -> _StubReport:
    if job.input.get("fail"):
        raise ValueError("Not worth a retry")
    return _StubReport(user_id=str(job.user_id))


async def _work_once_killed(job: Job) -> _StubReport:
    started = Path(job.input["started_file"])

    # Runs in the process the test kills, which never saves its coverage
    if not started.exists():  # pragma: no cover
        started.write_text(str(os.getpid()))
        time.sleep(60)

    return await _work(job)


async def _create_user(email: str) -> None:
    wiring = get_wiring()
    await create_user(
        UserCreateInput(email=email, password=PASSWORD),
        uow=wiring.build_unit_of_work(),
        password_hasher=wiring.build_password_hasher(),
    )
