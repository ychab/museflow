import os
import signal
from pathlib import Path
from typing import Final

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import anyio
from kombu import Connection
from kombu import Message
from kombu import Queue

from museflow.infrastructure.adapters.database.models.user import UserModel
from museflow.infrastructure.entrypoints.worker.const import BATCH_QUEUE
from museflow.infrastructure.entrypoints.worker.const import DEAD_LETTER_QUEUE
from museflow.infrastructure.entrypoints.worker.const import INTERACTIVE_QUEUE

from tests.integration.infrastructure.entrypoints.worker.celery_worker import CeleryWorker
from tests.integration.infrastructure.entrypoints.worker.stub_tasks import create_user_after_transient_error_task
from tests.integration.infrastructure.entrypoints.worker.stub_tasks import create_user_as_playlist_task
from tests.integration.infrastructure.entrypoints.worker.stub_tasks import create_user_once_killed_task
from tests.integration.infrastructure.entrypoints.worker.stub_tasks import create_user_task
from tests.integration.infrastructure.entrypoints.worker.stub_tasks import fail_task

# Long enough for a worker to take a task and run it, retries and a lost process included
WAIT_TIMEOUT_SECONDS: Final[float] = 30.0


class TestCeleryApp:
    async def test__task__nominal(self, worker: CeleryWorker, async_session_trans: AsyncSession) -> None:
        create_user_task.delay("worker@example.com")

        assert await self._wait_for_user(async_session_trans, "worker@example.com")

    async def test__task__default__batch_queue(
        self,
        broker_url: str,
        database_uri: str,
        file_storage_dir: Path,
        tmp_path: Path,
        async_session_trans: AsyncSession,
    ) -> None:
        # A worker of that queue only: it runs the task only if the task went there
        with CeleryWorker(
            broker_url=broker_url,
            database_uri=database_uri,
            file_storage_dir=file_storage_dir,
            log_file=tmp_path / "worker.log",
            queues=[BATCH_QUEUE.name],
        ):
            create_user_task.delay("batch@example.com")

            assert await self._wait_for_user(async_session_trans, "batch@example.com")

    async def test__task__playlist__interactive_queue(
        self,
        broker_url: str,
        database_uri: str,
        file_storage_dir: Path,
        tmp_path: Path,
        async_session_trans: AsyncSession,
    ) -> None:
        with CeleryWorker(
            broker_url=broker_url,
            database_uri=database_uri,
            file_storage_dir=file_storage_dir,
            log_file=tmp_path / "worker.log",
            queues=[INTERACTIVE_QUEUE.name],
        ):
            create_user_as_playlist_task.delay("interactive@example.com")

            assert await self._wait_for_user(async_session_trans, "interactive@example.com")

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

        result = fail_task.delay("failed@example.com")

        message = await self._wait_for_message(dead_letter_queue, result.id)
        assert message.headers["task"] == "tests.fail"
        assert "Retry in" not in worker.logs

    async def test__task__worker_killed__redelivered(
        self,
        worker: CeleryWorker,
        broker_url: str,
        database_uri: str,
        file_storage_dir: Path,
        tmp_path: Path,
        async_session_trans: AsyncSession,
    ) -> None:
        started_file = tmp_path / "started"

        create_user_once_killed_task.delay("redelivered@example.com", str(started_file))
        await self._wait_for_file(started_file)
        worker.kill()

        # The message was never acknowledged: RabbitMQ hands it to the next worker
        with CeleryWorker(
            broker_url=broker_url,
            database_uri=database_uri,
            file_storage_dir=file_storage_dir,
            log_file=tmp_path / "next.log",
        ):
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
    async def _wait_for_message(queue: Queue, task_id: str) -> Message:
        """The message of the task: the dead-letter queue also holds those of the other tests of the session."""
        with anyio.fail_after(WAIT_TIMEOUT_SECONDS):
            while (message := queue.get(no_ack=True)) is None or message.headers["id"] != task_id:
                await anyio.sleep(0.2)

        return message
