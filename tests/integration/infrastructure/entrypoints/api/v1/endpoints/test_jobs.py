import dataclasses
import uuid

from fastapi import status
from httpx import AsyncClient

from museflow.application.inputs.enrich import EnrichTracksJobInput
from museflow.application.use_cases.track_enrich import EnrichTracksReport
from museflow.application.use_cases.track_history_import import ImportStreamingHistoryReport
from museflow.domain.entities.user import User
from museflow.domain.enums import JobKind
from museflow.domain.enums import JobStatus
from museflow.infrastructure.entrypoints.api.main import app

from tests.integration.factories.models.job import JobModelFactory


class TestJobList:
    async def test__not_authenticated(self, async_client: AsyncClient) -> None:
        response = await async_client.get(app.url_path_for("job_list"))

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test__nominal(self, user: User, access_token: str, async_client: AsyncClient) -> None:
        report = ImportStreamingHistoryReport(items_read=6, plays_total=4, plays_created=4, tracks_created=4)
        job_db = await JobModelFactory.create_async(
            user_id=user.id,
            status=JobStatus.DONE,
            input={"prefix": "history/1", "provider": "spotify", "min_ms_played": 30_000, "purge": False},
            result=dataclasses.asdict(report),
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
                # Where its files are stays internal
                "input": {"provider": "spotify", "min_ms_played": 30_000, "purge": False},
                "result": dataclasses.asdict(report),
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

    async def test__enrich__typed(self, user: User, access_token: str, async_client: AsyncClient) -> None:
        report = EnrichTracksReport(enriched_count=180, error_count=1)
        job_db = await JobModelFactory.create_async(
            user_id=user.id,
            kind=JobKind.TRACK_ENRICH,
            status=JobStatus.DONE,
            input=EnrichTracksJobInput().model_dump(mode="json"),
            result=dataclasses.asdict(report),
        )

        response = await async_client.get(app.url_path_for("job_get", job_id=str(job_db.id)))

        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert response_data["kind"] == "track_enrich"
        assert response_data["input"] == {"fields": ["genre", "locale", "mood"]}
        # No fingerprints asked for through the API: none to miss
        assert response_data["result"] == {"enriched_count": 180, "error_count": 1}

    async def test__other_user__not_found(self, user: User, access_token: str, async_client: AsyncClient) -> None:
        job_db = await JobModelFactory.create_async()

        response = await async_client.get(app.url_path_for("job_get", job_id=str(job_db.id)))

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"] == "Job not found"

    async def test__unknown__not_found(self, user: User, access_token: str, async_client: AsyncClient) -> None:
        response = await async_client.get(app.url_path_for("job_get", job_id=str(uuid.uuid4())))

        assert response.status_code == status.HTTP_404_NOT_FOUND
