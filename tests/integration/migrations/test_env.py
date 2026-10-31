import asyncio
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import cast

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import make_url
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

import pytest

from museflow.infrastructure.adapters.database.models.base import Base
from museflow.infrastructure.config.settings.database import database_settings

ROOT_DIR = Path(__file__).parents[3]


class TestMigrations:
    @pytest.fixture
    async def migration_db_url(self, test_db_name: str) -> AsyncGenerator[str]:
        db_name = f"{test_db_name}_migrations"
        admin_engine = create_async_engine(url=str(database_settings.URI), isolation_level="AUTOCOMMIT")
        async with admin_engine.connect() as conn:
            await conn.execute(text(f"DROP DATABASE IF EXISTS {db_name}"))
            await conn.execute(text(f"CREATE DATABASE {db_name}"))

        yield make_url(str(database_settings.URI)).set(database=db_name).render_as_string(hide_password=False)

        async with admin_engine.connect() as conn:
            await conn.execute(text(f"DROP DATABASE IF EXISTS {db_name}"))
        await admin_engine.dispose()

    async def test__upgrade_head__matches_models(self, migration_db_url: str) -> None:
        config = Config()
        config.set_main_option("script_location", str(ROOT_DIR / "migrations"))
        config.set_main_option("sqlalchemy.url", migration_db_url)

        # env.py calls asyncio.run(), which cannot run inside the test event loop.
        await asyncio.to_thread(command.upgrade, config, "head")

        def diff(connection: Connection) -> list[object]:
            return cast(list[object], compare_metadata(MigrationContext.configure(connection), Base.metadata))

        engine = create_async_engine(url=migration_db_url)
        try:
            async with engine.connect() as conn:
                assert await conn.run_sync(diff) == []
        finally:
            await engine.dispose()
