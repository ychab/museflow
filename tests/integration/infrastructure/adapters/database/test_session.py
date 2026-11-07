import asyncio
import uuid
from collections.abc import AsyncGenerator

from sqlalchemy import make_url
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.ext.asyncio import async_sessionmaker

import pytest

from museflow.infrastructure.adapters.database.session import create_engine
from museflow.infrastructure.adapters.database.unit_of_work import SQLUnitOfWork
from museflow.infrastructure.config.settings.database import database_settings


class TestCreateEngine:
    @pytest.fixture
    async def engine(self, request: pytest.FixtureRequest, test_db_name: str) -> AsyncGenerator[AsyncEngine]:
        url = make_url(str(database_settings.URI)).set(database=test_db_name)
        engine = create_engine(url.render_as_string(hide_password=False), idle_in_transaction_timeout=request.param)
        yield engine
        await engine.dispose()

    @pytest.mark.parametrize("engine", [60], indirect=True)
    async def test__idle_in_transaction_timeout__reaches_postgresql(self, engine: AsyncEngine) -> None:
        async with engine.connect() as conn:
            assert await conn.scalar(text("SHOW idle_in_transaction_session_timeout")) == "1min"

    @pytest.mark.parametrize("engine", [1], indirect=True)
    async def test__block_left_idle__fails_loudly(self, engine: AsyncEngine) -> None:
        unit_of_work = SQLUnitOfWork(async_sessionmaker(bind=engine, expire_on_commit=False))

        with pytest.raises(DBAPIError, match="connection is closed"):
            async with unit_of_work as uow:
                await uow.tracks.get_list(user_id=uuid.uuid4())
                await asyncio.sleep(1.5)  # A remote call inside the block, by mistake
                await uow.tracks.get_list(user_id=uuid.uuid4())
