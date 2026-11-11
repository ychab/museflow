from fastapi import status
from httpx import AsyncClient

from sqlalchemy.ext.asyncio import AsyncSession

from museflow.infrastructure.entrypoints.api.main import app


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
