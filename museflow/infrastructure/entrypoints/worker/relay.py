"""The relay: publishes the task messages of the jobs the API commits, the transactional outbox of the jobs table.

The API never publishes: it commits the job, unpublished, and a notification wakes the relay up. The relay runs as a
process of its own (`python -m museflow.infrastructure.entrypoints.worker.relay`), a single one: several would publish
the same jobs, which the workers would drop as duplicates. It sits with the worker, whose Celery app it publishes
through.
"""

import asyncio
import logging
import signal
from datetime import timedelta
from typing import Final

from museflow.application.ports.queue import JobPublisherPort
from museflow.application.use_cases.job_publish import publish_jobs
from museflow.infrastructure.adapters.database.listener import PostgresListener
from museflow.infrastructure.adapters.database.models import JOB_CHANNEL
from museflow.infrastructure.adapters.queue.celery import CeleryJobPublisher
from museflow.infrastructure.config.loggers.setup import configure_loggers
from museflow.infrastructure.config.settings.app import app_settings
from museflow.infrastructure.config.settings.database import database_settings
from museflow.infrastructure.entrypoints.wiring import Wiring
from museflow.infrastructure.entrypoints.worker.const import JOB_TASK_NAMES
from museflow.infrastructure.entrypoints.worker.const import TRANSIENT_ERRORS
from museflow.infrastructure.entrypoints.worker.main import celery_app

logger = logging.getLogger(__name__)


class JobRelay:
    """Publishes the unpublished jobs whenever a new one is notified, and at every poll for the notifications missed."""

    # The longest a job waits when its notification was lost (the relay restarting, the listener reconnecting)
    POLL_INTERVAL: Final[timedelta] = timedelta(seconds=5)
    # Jobs read per round: a full round goes on at once with the next ones
    BATCH_SIZE: Final[int] = 100

    def __init__(self, wiring: Wiring, job_publisher: JobPublisherPort, database_uri: str) -> None:
        self._wiring = wiring
        self._job_publisher = job_publisher
        self._wake = asyncio.Event()
        self._listener = PostgresListener(database_uri, channel=JOB_CHANNEL, on_notify=self._wake.set)

    async def run(self, stop: asyncio.Event) -> None:
        """Relays until `stop` is set; a round under way ends first."""
        async with self._listener:
            while not stop.is_set():
                # Cleared before the round: a job notified during it starts the next one at once
                self._wake.clear()

                published = await self._publish()
                if published == self.BATCH_SIZE:
                    continue

                await self._wait(stop)
                await self._listener.ensure_listening()

    async def _publish(self) -> int:
        try:
            published = await publish_jobs(
                self.BATCH_SIZE,
                uow=self._wiring.build_unit_of_work(),
                job_publisher=self._job_publisher,
            )
        except TRANSIENT_ERRORS:
            logger.warning(
                "Jobs not relayed, the database is unreachable: tried again on the next poll", exc_info=True
            )
            published = 0

        if published:
            logger.info(f"{published} job(s) published", extra={"published_count": published})
        return published

    async def _wait(self, stop: asyncio.Event) -> None:
        """Until a job is notified, the relay is stopped, or the poll interval is over."""
        waits = [asyncio.create_task(self._wake.wait()), asyncio.create_task(stop.wait())]
        await asyncio.wait(waits, timeout=self.POLL_INTERVAL.total_seconds(), return_when=asyncio.FIRST_COMPLETED)

        for wait in waits:
            wait.cancel()


def main() -> None:
    configure_loggers(
        level=app_settings.LOG_LEVEL_WORKER,
        third_party_level=app_settings.LOG_LEVEL_THIRD_PARTY,
        handlers=app_settings.LOG_HANDLERS_WORKER,
    )
    asyncio.run(_relay())


async def _relay() -> None:
    # `docker compose stop` sends SIGTERM: the round under way ends, then the relay stops
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(signum, stop.set)

    async with Wiring.open() as wiring:
        relay = JobRelay(
            wiring=wiring,
            job_publisher=CeleryJobPublisher(celery_app, task_names=JOB_TASK_NAMES),
            database_uri=str(database_settings.URI),
        )
        logger.info("Relay started")
        await relay.run(stop)

    logger.info("Relay stopped")


if __name__ == "__main__":
    main()
