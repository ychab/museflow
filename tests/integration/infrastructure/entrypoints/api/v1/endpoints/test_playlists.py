from fastapi import status
from httpx import AsyncClient

import pytest

from museflow.domain.entities.user import User
from museflow.domain.enums import PlaylistType
from museflow.infrastructure.entrypoints.api.const import PAGE_LIMIT_MAX
from museflow.infrastructure.entrypoints.api.main import app

from tests.integration.factories.models.playlist import PlaylistModelFactory
from tests.integration.factories.models.user import UserModelFactory


class TestPlaylistList:
    async def test__not_authenticated(self, async_client: AsyncClient) -> None:
        response = await async_client.get(app.url_path_for("playlist_list"))

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.headers["content-type"] == "application/problem+json"
        assert response.headers["www-authenticate"] == "Bearer"
        assert response.json()["detail"] == "Not authenticated"

    async def test__nominal(self, user: User, access_token: str, async_client: AsyncClient) -> None:
        playlists_db = [await PlaylistModelFactory.create_async(user_id=user.id) for _ in range(3)]

        response = await async_client.get(app.url_path_for("playlist_list"), params={"limit": 2, "offset": 1})

        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        # The newest first: the page skips the newest one, the total counts every page
        assert [item["id"] for item in response_data["items"]] == [str(playlists_db[1].id), str(playlists_db[0].id)]
        assert response_data["total"] == 3
        assert (response_data["limit"], response_data["offset"]) == (2, 1)
        assert response_data["items"][0] == {
            "id": str(playlists_db[1].id),
            "name": playlists_db[1].name,
            "type": playlists_db[1].type.value,
            "provider": playlists_db[1].provider.value,
            "provider_id": playlists_db[1].provider_id,
            "prompt": playlists_db[1].prompt,
            "focus": playlists_db[1].focus.value if playlists_db[1].focus else None,
            "created_at": playlists_db[1].created_at.isoformat().replace("+00:00", "Z"),
        }

    async def test__default_page(self, user: User, access_token: str, async_client: AsyncClient) -> None:
        response = await async_client.get(app.url_path_for("playlist_list"))

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {"items": [], "total": 0, "limit": 20, "offset": 0}

    async def test__type(self, user: User, access_token: str, async_client: AsyncClient) -> None:
        explore_db = await PlaylistModelFactory.create_async(user_id=user.id, type=PlaylistType.EXPLORE)
        await PlaylistModelFactory.create_async(user_id=user.id, type=PlaylistType.DISCOVERY)

        response = await async_client.get(app.url_path_for("playlist_list"), params={"type": PlaylistType.EXPLORE})

        assert response.status_code == status.HTTP_200_OK
        assert [item["id"] for item in response.json()["items"]] == [str(explore_db.id)]

    async def test__other_user(self, user: User, access_token: str, async_client: AsyncClient) -> None:
        other_user_db = await UserModelFactory.create_async()
        await PlaylistModelFactory.create_async(user_id=other_user_db.id)

        response = await async_client.get(app.url_path_for("playlist_list"))

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["total"] == 0

    @pytest.mark.parametrize(
        ("params", "field"),
        [
            ({"limit": 0}, "limit"),
            ({"limit": PAGE_LIMIT_MAX + 1}, "limit"),
            ({"offset": -1}, "offset"),
        ],
    )
    async def test__page__out_of_bounds(
        self,
        params: dict[str, int],
        field: str,
        access_token: str,
        async_client: AsyncClient,
    ) -> None:
        url = app.url_path_for("playlist_list")

        response = await async_client.get(url, params=params)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert response.headers["content-type"] == "application/problem+json"
        response_data = response.json()
        assert response_data["detail"] == "The request is invalid"
        assert response_data["instance"] == url
        assert response_data["errors"][0]["loc"] == ["query", field]
