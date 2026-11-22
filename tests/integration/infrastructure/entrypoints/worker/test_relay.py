import os
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Final

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import anyio
import pytest
from kombu import Message
from kombu import Queue

from museflow.domain.entities.job import Job
from museflow.domain.enums import JobKind
from museflow.infrastructure.adapters.database.models import JobModel
from museflow.infrastructure.adapters.database.repositories.job import JobSQLRepository

from tests.integration.factories.models.job import JobModelFactory
from tests.integration.factories.models.user import UserModelFactory

WAIT_TIMEOUT_SECONDS: Final[float] = 30.0


class TestRelay:
    @pytest.fixture
    def log_file(self, tmp_path: Path) -> Iterator[Path]:
        log_file = tmp_path / "relay.log"
        yield log_file
        # Shown for a failed test only
        print(log_file.read_text() if log_file.exists() else "")

    @pytest.fixture
    def relay(
        self,
        broker_url: str,
        database_uri: str,
        log_file: Path,
        batch_queue: Queue,
    ) -> Iterator[subprocess.Popen[bytes]]:
        """The relay, run as `docker compose` does, on the test database and virtual host."""
        env = {
            **os.environ,
            "BROKER_URL": broker_url,
            "DATABASE_URI": database_uri,
            "MUSEFLOW_LOG_HANDLERS_WORKER": '["console"]',
        }
        command = [sys.executable, "-m", "museflow.infrastructure.entrypoints.worker.relay"]

        with log_file.open("ab") as log:
            process = subprocess.Popen(command, env=env, stdout=log, stderr=subprocess.STDOUT)

        yield process

        if process.poll() is None:
            process.kill()
            process.wait()

    async def test__nominal(
        self,
        async_session_trans: AsyncSession,
        relay: subprocess.Popen[bytes],
        log_file: Path,
        batch_queue: Queue,
    ) -> None:
        # Committed before the relay listens: no notification heard, its first round finds it
        job_before_db = await JobModelFactory.create_async()
        await async_session_trans.commit()

        message = await self._wait_for_message(batch_queue)
        assert message.decode()[0] == [str(job_before_db.id), str(job_before_db.user_id)]

        # Created as the API does, while it listens: the notification wakes it up, well before its next poll
        await self._wait_for_log(log_file, "Relay started")
        user_db = await UserModelFactory.create_async()
        job_after = await JobSQLRepository(async_session_trans).create(
            Job(user_id=user_db.id, kind=JobKind.TRACK_HISTORY_IMPORT)
        )
        await async_session_trans.commit()

        message = await self._wait_for_message(batch_queue, timeout=3.0)
        assert message.decode()[0] == [str(job_after.id), str(job_after.user_id)]

        # Stopped as `docker compose stop` asks
        relay.terminate()
        assert relay.wait(timeout=10) == 0
        assert "Relay stopped" in log_file.read_text()
        published = (await async_session_trans.scalars(select(JobModel.published_at))).all()
        assert len(published) == 2
        assert all(published_at is not None for published_at in published)

    @staticmethod
    async def _wait_for_message(queue: Queue, timeout: float = WAIT_TIMEOUT_SECONDS) -> Message:
        with anyio.fail_after(timeout):
            while (message := queue.get(no_ack=True)) is None:
                await anyio.sleep(0.1)

        return message

    @staticmethod
    async def _wait_for_log(log_file: Path, text: str) -> None:
        with anyio.fail_after(WAIT_TIMEOUT_SECONDS):
            while not (log_file.exists() and text in log_file.read_text()):
                await anyio.sleep(0.1)
