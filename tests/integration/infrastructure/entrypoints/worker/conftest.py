import os
from collections.abc import Iterator
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.ext.asyncio import AsyncSession

import pytest
from kombu import Connection

from museflow.infrastructure.config.settings.broker import broker_settings
from museflow.infrastructure.entrypoints.worker.main import celery_app

from tests.integration.utils.celery_worker import CeleryWorker


@pytest.fixture(scope="session")
def broker_url(worker_id: str) -> Iterator[str]:
    """The URL of a RabbitMQ virtual host of the test process, created for the session.

    Its own queues: no other worker (the one of `make up`, the one of another xdist process) takes its tasks.
    """
    url = urlsplit(broker_settings.URL.get_secret_value())  # type: ignore[union-attr]
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
