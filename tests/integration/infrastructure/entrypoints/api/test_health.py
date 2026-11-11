from collections.abc import AsyncGenerator

from fastapi import status
from httpx import AsyncClient

from sqlalchemy import make_url
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine

import pytest

from museflow.infrastructure.config.settings.database import database_settings
from museflow.infrastructure.entrypoints.api.main import app


@pytest.fixture
async def unavailable_db_session(test_db_name: str) -> AsyncGenerator[AsyncSession]:
    """A session on a database that doesn't exist: its first query fails with PostgreSQL's real error."""
    url = make_url(str(database_settings.URI)).set(database=f"{test_db_name}_missing")
    engine = create_async_engine(url)
    async with async_sessionmaker(engine)() as session:
        yield session
    await engine.dispose()


class TestHealthCheck:
    async def test__healthy(self, async_client: AsyncClient) -> None:
        url = app.url_path_for("health_check")
        response = await async_client.get(url)
        assert response.status_code == status.HTTP_200_OK

        response_data = response.json()
        assert response_data == {
            "status": "healthy",
            "database": "connected",
        }

    async def test__unhealthy(self, unavailable_db_session: AsyncSession, async_client: AsyncClient) -> None:
        url = app.url_path_for("health_check")
        response = await async_client.get(url)
        assert response.status_code == status.HTTP_200_OK

        response_data = response.json()
        assert response_data == {
            "status": "unhealthy",
            "database": "unavailable",
        }
