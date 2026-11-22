import uuid

from fastapi import status
from httpx import AsyncClient

from museflow.domain.entities.user import User
from museflow.domain.enums import JobStatus
from museflow.infrastructure.entrypoints.api.main import app

from tests.integration.factories.models.job import JobModelFactory


class TestJobList:
    async def test__not_authenticated(self, async_client: AsyncClient) -> None:
        response = await async_client.get(app.url_path_for("job_list"))

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test__nominal(self, user: User, access_token: str, async_client: AsyncClient) -> None:
        job_db = await JobModelFactory.create_async(
            user_id=user.id,
            status=JobStatus.DONE,
            input={"chunk_size": 500},
            result={"tracks_count": 12},
        )
        await JobModelFactory.create_async()

        response = await async_client.get(app.url_path_for("job_list"))

        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert response_data["total"] == 1
        assert response_data["items"] == [
            {
                "id": str(job_db.id),
                "kind": job_db.kind.value,
                "status": "done",
                "input": {"chunk_size": 500},
                "result": {"tracks_count": 12},
                "error": None,
                "created_at": job_db.created_at.isoformat().replace("+00:00", "Z"),
                "started_at": None,
                "finished_at": None,
            }
        ]


class TestJobGet:
    async def test__nominal(self, user: User, access_token: str, async_client: AsyncClient) -> None:
        job_db = await JobModelFactory.create_async(user_id=user.id)

        response = await async_client.get(app.url_path_for("job_get", job_id=str(job_db.id)))

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["status"] == "pending"

    async def test__other_user__not_found(self, user: User, access_token: str, async_client: AsyncClient) -> None:
        job_db = await JobModelFactory.create_async()

        response = await async_client.get(app.url_path_for("job_get", job_id=str(job_db.id)))

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"] == "Job not found"

    async def test__unknown__not_found(self, user: User, access_token: str, async_client: AsyncClient) -> None:
        response = await async_client.get(app.url_path_for("job_get", job_id=str(uuid.uuid4())))

        assert response.status_code == status.HTTP_404_NOT_FOUND
