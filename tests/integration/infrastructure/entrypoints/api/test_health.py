from unittest.mock import AsyncMock

from fastapi import status
from httpx import AsyncClient

from museflow.infrastructure.entrypoints.api.main import app


class TestHealthCheck:
    async def test_healthy(self, async_client: AsyncClient) -> None:
        url = app.url_path_for("health_check")
        response = await async_client.get(url)
        assert response.status_code == status.HTTP_200_OK

        response_data = response.json()
        assert response_data == {
            "status": "healthy",
            "database": "connected",
        }

    async def test_unhealthy(self, mock_db_session: AsyncMock, async_client: AsyncClient) -> None:
        mock_db_session.execute.side_effect = Exception("Boom")

        url = app.url_path_for("health_check")
        response = await async_client.get(url)
        assert response.status_code == status.HTTP_200_OK

        response_data = response.json()
        assert response_data == {
            "status": "unhealthy",
            "database": "error: Boom",
        }
