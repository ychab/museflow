import os
import signal
from collections.abc import Iterator
from pathlib import Path
from typing import Final
from urllib.parse import urlsplit

import httpx

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.ext.asyncio import AsyncSession

import anyio
import pytest
from kombu import Connection
from kombu import Message
from kombu import Queue

from museflow.infrastructure.adapters.database.models.user import UserModel
from museflow.infrastructure.config.settings.broker import broker_settings
from museflow.infrastructure.entrypoints.worker.app import DEAD_LETTER_QUEUE
from museflow.infrastructure.entrypoints.worker.app import celery_app

from tests.integration.utils.celery_tasks import create_user_after_transient_error_task
from tests.integration.utils.celery_tasks import create_user_once_killed_task
from tests.integration.utils.celery_tasks import create_user_task
from tests.integration.utils.celery_tasks import fail_task
from tests.integration.utils.celery_worker import CeleryWorker

# Long enough for a worker to take a task and run it, retries and a lost process included
WAIT_TIMEOUT_SECONDS: Final[float] = 30.0


@pytest.fixture(scope="session")
def broker_url(worker_id: str) -> Iterator[str]:
    """The URL of a RabbitMQ virtual host of the test process, created for the session.

    Its own queues: no other worker (the one of `make up`, the one of another xdist process) takes its tasks.
    """
    url = urlsplit(broker_settings.URL.get_secret_value())
    vhost = f"test_museflow_{worker_id}"
    test_url = url._replace(path=f"/{vhost}").geturl()

    with httpx.Client(
        base_url=os.environ["BROKER_MANAGEMENT_URL"],
        auth=(url.username or "", url.password or ""),
    ) as management:
        # A virtual host left by an interrupted session would still hold its messages
        management.delete(f"/api/vhosts/{vhost}")
        management.put(f"/api/vhosts/{vhost}").raise_for_status()
        management.put(
            f"/api/permissions/{vhost}/{url.username}",
            json={"configure": ".*", "write": ".*", "read": ".*"},
        ).raise_for_status()

        with pytest.MonkeyPatch.context() as monkeypatch:
            monkeypatch.setattr(celery_app.conf, "broker_url", test_url)
            yield test_url

        management.delete(f"/api/vhosts/{vhost}").raise_for_status()


@pytest.fixture
def database_uri(async_engine: AsyncEngine) -> str:
    return async_engine.url.render_as_string(hide_password=False)


@pytest.fixture
def worker(
    broker_url: str,
    database_uri: str,
    tmp_path: Path,
    async_session_trans: AsyncSession,
) -> Iterator[CeleryWorker]:
    """A worker on the test database: its tasks commit, so the test reads with `async_session_trans`.

    Its logs print at the end, which pytest shows for a failed test only.
    """
    with CeleryWorker(broker_url=broker_url, database_uri=database_uri, log_file=tmp_path / "worker.log") as worker:
        yield worker

    print(worker.logs)


@pytest.fixture
def broker_connection(broker_url: str) -> Iterator[Connection]:
    with celery_app.connection_for_write() as connection:
        yield connection


class TestCeleryApp:
    async def test__task__nominal(self, worker: CeleryWorker, async_session_trans: AsyncSession) -> None:
        create_user_task.delay("worker@example.com")

        assert await self._wait_for_user(async_session_trans, "worker@example.com")

    async def test__task__transient_error__retried(
        self,
        worker: CeleryWorker,
        async_session_trans: AsyncSession,
    ) -> None:
        create_user_after_transient_error_task.delay("retried@example.com")

        assert await self._wait_for_user(async_session_trans, "retried@example.com")
        assert "Retry in" in worker.logs

    async def test__task__error__dead_lettered(
        self,
        worker: CeleryWorker,
        broker_connection: Connection,
    ) -> None:
        dead_letter_queue = DEAD_LETTER_QUEUE(broker_connection.default_channel)
        dead_letter_queue.purge()

        fail_task.delay("failed@example.com")

        message = await self._wait_for_message(dead_letter_queue)
        assert message.headers["task"] == "tests.fail"
        assert "Retry in" not in worker.logs

    async def test__task__worker_killed__redelivered(
        self,
        worker: CeleryWorker,
        broker_url: str,
        database_uri: str,
        tmp_path: Path,
        async_session_trans: AsyncSession,
    ) -> None:
        started_file = tmp_path / "started"

        create_user_once_killed_task.delay("redelivered@example.com", str(started_file))
        await self._wait_for_file(started_file)
        worker.kill()

        # The message was never acknowledged: RabbitMQ hands it to the next worker
        with CeleryWorker(broker_url=broker_url, database_uri=database_uri, log_file=tmp_path / "next.log"):
            assert await self._wait_for_user(async_session_trans, "redelivered@example.com")

    async def test__task__process_killed__retried(
        self,
        worker: CeleryWorker,
        tmp_path: Path,
        async_session_trans: AsyncSession,
    ) -> None:
        started_file = tmp_path / "started"

        create_user_once_killed_task.delay("lost@example.com", str(started_file))
        await self._wait_for_file(started_file)
        # The process running the task only, as the out-of-memory killer would: the worker forks another one
        os.kill(int(started_file.read_text()), signal.SIGKILL)

        assert await self._wait_for_user(async_session_trans, "lost@example.com")
        assert "WorkerLostError" in worker.logs

    @staticmethod
    async def _wait_for_user(session: AsyncSession, email: str) -> UserModel:
        with anyio.fail_after(WAIT_TIMEOUT_SECONDS):
            while (user_db := await session.scalar(select(UserModel).where(UserModel.email == email))) is None:
                await anyio.sleep(0.2)

        return user_db

    @staticmethod
    async def _wait_for_file(path: Path) -> None:
        with anyio.fail_after(WAIT_TIMEOUT_SECONDS):
            while not (path.exists() and path.read_text()):
                await anyio.sleep(0.2)

    @staticmethod
    async def _wait_for_message(queue: Queue) -> Message:
        with anyio.fail_after(WAIT_TIMEOUT_SECONDS):
            while (message := queue.get(no_ack=True)) is None:
                await anyio.sleep(0.2)

        return message
