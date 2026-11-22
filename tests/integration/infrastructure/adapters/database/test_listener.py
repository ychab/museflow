import asyncio
import logging
from typing import Final

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

import anyio
import pytest

from museflow.infrastructure.adapters.database.listener import PostgresListener

CHANNEL: Final[str] = "museflow_test"


class TestPostgresListener:
    @pytest.fixture
    def notified(self) -> asyncio.Event:
        return asyncio.Event()

    @pytest.fixture
    def listener(self, database_uri: str, notified: asyncio.Event) -> PostgresListener:
        return PostgresListener(database_uri, channel=CHANNEL, on_notify=notified.set)

    async def _notify(self, async_engine: AsyncEngine) -> None:
        async with async_engine.begin() as conn:
            await conn.execute(text(f"NOTIFY {CHANNEL}"))

    async def test__nominal(
        self,
        async_engine: AsyncEngine,
        listener: PostgresListener,
        notified: asyncio.Event,
    ) -> None:
        async with listener:
            await self._notify(async_engine)

            with anyio.fail_after(5):
                await notified.wait()

    async def test__ensure_listening__connection_dropped(
        self,
        async_engine: AsyncEngine,
        listener: PostgresListener,
        notified: asyncio.Event,
    ) -> None:
        async with listener:
            # As a database restart would
            async with async_engine.begin() as conn:
                await conn.execute(
                    text(
                        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                        "WHERE datname = current_database() AND pid <> pg_backend_pid() AND query LIKE 'LISTEN%'"
                    )
                )
            with anyio.fail_after(5):
                while not listener._connection.is_closed():  # type: ignore[union-attr]
                    await anyio.sleep(0.1)

            await listener.ensure_listening()
            await self._notify(async_engine)

            with anyio.fail_after(5):
                await notified.wait()

    async def test__ensure_listening__database_unreachable(
        self,
        caplog: pytest.LogCaptureFixture,
        notified: asyncio.Event,
    ) -> None:
        listener = PostgresListener(
            "postgresql+asyncpg://museflow:museflow@127.0.0.1:1/museflow",
            channel=CHANNEL,
            on_notify=notified.set,
        )

        with caplog.at_level(logging.WARNING):
            async with listener:
                pass

        assert f"Not listening to {CHANNEL}" in caplog.text
