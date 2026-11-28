from datetime import UTC
from datetime import datetime
from datetime import timedelta

from fastapi import status
from httpx import AsyncClient

import pytest

from museflow.domain.entities.user import User
from museflow.domain.enums import JobStatus
from museflow.domain.enums import TasteProfileStatus
from museflow.infrastructure.entrypoints.api.main import app

from tests.integration.factories.models.taste import TasteProfileBuildModelFactory
from tests.integration.factories.models.taste import TasteProfileModelFactory


class TestTasteProfileBuild:
    @pytest.fixture
    def url(self) -> str:
        return app.url_path_for("taste_profile_build")

    async def test__not_authenticated(self, url: str, async_client: AsyncClient) -> None:
        response = await async_client.post(url, json={"title": "Winter"})

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test__nominal(self, url: str, user: User, access_token: str, async_client: AsyncClient) -> None:
        response = await async_client.post(url, json={"title": "Soirées d'hiver", "rated_only": True})

        assert response.status_code == status.HTTP_202_ACCEPTED
        response_data = response.json()
        assert response.headers["Location"] == app.url_path_for("job_get", job_id=response_data["id"])
        assert response_data["kind"] == "taste_build"
        assert response_data["status"] == JobStatus.PENDING
        assert response_data["input"] == {"name": "soirees-d-hiver", "title": "Soirées d'hiver", "rated_only": True}
        assert response_data["result"] is None

    async def test__title__no_slug(self, url: str, access_token: str, async_client: AsyncClient) -> None:
        response = await async_client.post(url, json={"title": "!!!"})

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test__finished(self, url: str, user: User, access_token: str, async_client: AsyncClient) -> None:
        await TasteProfileModelFactory.create_async(user_id=user.id, name="winter")

        response = await async_client.post(url, json={"title": "Winter"})

        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.json()["detail"] == "This taste profile is already built: delete it to build it again"


class TestTasteProfileList:
    async def test__not_authenticated(self, async_client: AsyncClient) -> None:
        response = await async_client.get(app.url_path_for("taste_profile_list"))

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test__nominal(self, user: User, access_token: str, async_client: AsyncClient) -> None:
        profiles_db = [await TasteProfileModelFactory.create_async(user_id=user.id) for _ in range(3)]
        await TasteProfileModelFactory.create_async()  # Another user

        response = await async_client.get(app.url_path_for("taste_profile_list"), params={"limit": 2, "offset": 1})

        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        # The last updated first: the page skips the latest one, the total counts every page
        assert [item["id"] for item in response_data["items"]] == [str(profiles_db[1].id), str(profiles_db[0].id)]
        assert response_data["total"] == 3
        # A summary: the data stays in the profile's own route
        assert response_data["items"][0] == {
            "id": str(profiles_db[1].id),
            "name": profiles_db[1].name,
            "title": profiles_db[1].title,
            "status": "finished",
            "tracks_count": profiles_db[1].tracks_count,
            "logic_version": profiles_db[1].logic_version,
            "created_at": profiles_db[1].created_at.isoformat().replace("+00:00", "Z"),
            "updated_at": profiles_db[1].updated_at.isoformat().replace("+00:00", "Z"),
        }


class TestTasteProfileGet:
    async def test__nominal(self, user: User, access_token: str, async_client: AsyncClient) -> None:
        profile_db = await TasteProfileModelFactory.create_async(user_id=user.id, name="main")

        response = await async_client.get(app.url_path_for("taste_profile_get", name="main"))

        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert response_data["id"] == str(profile_db.id)
        assert response_data["profile"]["core_identity"] == profile_db.profile["core_identity"]
        assert len(response_data["profile"]["taste_timeline"]) == len(profile_db.profile["taste_timeline"])
        assert "profiler_metadata" not in response_data

    async def test__building(self, user: User, access_token: str, async_client: AsyncClient) -> None:
        await TasteProfileModelFactory.create_async(user_id=user.id, name="main", status=TasteProfileStatus.BUILDING)

        response = await async_client.get(app.url_path_for("taste_profile_get", name="main"))

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["status"] == "building"

    async def test__other_user__not_found(self, user: User, access_token: str, async_client: AsyncClient) -> None:
        await TasteProfileModelFactory.create_async(name="main")

        response = await async_client.get(app.url_path_for("taste_profile_get", name="main"))

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"] == "Taste profile not found"

    @pytest.mark.parametrize("name", ["my profile", "é", "a" * 65])
    async def test__name__invalid(self, name: str, access_token: str, async_client: AsyncClient) -> None:
        response = await async_client.get(app.url_path_for("taste_profile_get", name=name))

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert response.json()["errors"][0]["loc"] == ["path", "name"]


class TestTasteProfileDelete:
    async def test__nominal(self, user: User, access_token: str, async_client: AsyncClient) -> None:
        await TasteProfileModelFactory.create_async(user_id=user.id, name="main")

        response = await async_client.delete(app.url_path_for("taste_profile_delete", name="main"))

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert response.content == b""
        response = await async_client.get(app.url_path_for("taste_profile_get", name="main"))
        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test__other_user__not_found(self, user: User, access_token: str, async_client: AsyncClient) -> None:
        other_db = await TasteProfileModelFactory.create_async(name="main")

        response = await async_client.delete(app.url_path_for("taste_profile_delete", name="main"))

        assert response.status_code == status.HTTP_404_NOT_FOUND
        # The other user's profile is untouched
        assert other_db.name == "main"

    async def test__build_running(self, user: User, access_token: str, async_client: AsyncClient) -> None:
        await TasteProfileModelFactory.create_async(user_id=user.id, name="main", status=TasteProfileStatus.BUILDING)
        await TasteProfileBuildModelFactory.create_async(
            user_id=user.id,
            name="main",
            lease_until=datetime.now(UTC) + timedelta(minutes=10),
        )

        response = await async_client.delete(app.url_path_for("taste_profile_delete", name="main"))

        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.json()["detail"] == "A build of this taste profile is running"
