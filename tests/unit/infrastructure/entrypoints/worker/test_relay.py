import asyncio
import logging
from collections.abc import Iterator
from unittest import mock

from sqlalchemy.exc import OperationalError

import pytest

from museflow.application.ports.queue import JobPublisherPort
from museflow.infrastructure.entrypoints.wiring import Wiring
from museflow.infrastructure.entrypoints.worker.relay import JobRelay

TARGET_PATH = "museflow.infrastructure.entrypoints.worker.relay"


class TestJobRelay:
    @pytest.fixture
    def mock_publish_jobs(self) -> Iterator[mock.AsyncMock]:
        with mock.patch(f"{TARGET_PATH}.publish_jobs", new_callable=mock.AsyncMock) as patched:
            yield patched

    @pytest.fixture
    def mock_listener(self) -> Iterator[mock.Mock]:
        with mock.patch(f"{TARGET_PATH}.PostgresListener") as patched:
            listener = patched.return_value
            listener.__aenter__ = mock.AsyncMock(return_value=listener)
            listener.__aexit__ = mock.AsyncMock(return_value=None)
            listener.ensure_listening = mock.AsyncMock()
            yield listener

    @pytest.fixture
    def relay(self, mock_listener: mock.Mock) -> JobRelay:
        return JobRelay(
            wiring=mock.Mock(spec=Wiring),
            job_publisher=mock.AsyncMock(spec=JobPublisherPort),
            database_uri="postgresql+asyncpg://museflow:museflow@127.0.0.1/museflow",
        )

    async def test__full_round__next_at_once(self, relay: JobRelay, mock_publish_jobs: mock.AsyncMock) -> None:
        stop = asyncio.Event()

        def round_(*args: object, **kwargs: object) -> int:
            if mock_publish_jobs.await_count == 2:
                stop.set()
                return 0
            return JobRelay.BATCH_SIZE

        mock_publish_jobs.side_effect = round_

        # A full round would wait for the poll otherwise: well over the timeout
        async with asyncio.timeout(1):
            await relay.run(stop)

        assert mock_publish_jobs.await_count == 2

    async def test__database_unreachable(
        self,
        caplog: pytest.LogCaptureFixture,
        relay: JobRelay,
        mock_publish_jobs: mock.AsyncMock,
    ) -> None:
        stop = asyncio.Event()

        def unreachable(*args: object, **kwargs: object) -> int:
            stop.set()
            raise OperationalError("SELECT", {}, ConnectionRefusedError())

        mock_publish_jobs.side_effect = unreachable

        with caplog.at_level(logging.WARNING):
            await relay.run(stop)

        assert "Jobs not relayed, the database is unreachable" in caplog.text
