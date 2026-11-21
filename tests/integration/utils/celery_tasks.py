import os
import time
from pathlib import Path
from typing import Final

from celery import Task

from museflow.application.inputs.user import UserCreateInput
from museflow.application.use_cases.user_create import create_user
from museflow.infrastructure.entrypoints.worker.dependencies import get_wiring
from museflow.infrastructure.entrypoints.worker.dependencies import run_task
from museflow.infrastructure.entrypoints.worker.main import celery_app

# Tasks that prove the worker setup, loaded by the test workers only (`celery worker --include`). Each one runs a use
# case against the database, as a real task does: the test sees it ran from the user it created.

PASSWORD: Final[str] = "a-test-password"


@celery_app.task(name="tests.create_user")
def create_user_task(email: str) -> None:
    run_task(_create_user(email))


@celery_app.task(name="tests.create_user_after_transient_error", bind=True)
def create_user_after_transient_error_task(self: Task[[str], None], email: str) -> None:
    if self.request.retries == 0:
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


async def _create_user(email: str) -> None:
    wiring = get_wiring()
    await create_user(
        UserCreateInput(email=email, password=PASSWORD),
        uow=wiring.build_unit_of_work(),
        password_hasher=wiring.build_password_hasher(),
    )
