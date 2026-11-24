from fastapi import status
from httpx import AsyncClient

import pytest

from museflow.domain.entities.user import User
from museflow.domain.enums import JobStatus
from museflow.infrastructure.adapters.storage.local import LocalFileStorage
from museflow.infrastructure.config.settings.app import app_settings
from museflow.infrastructure.entrypoints.api.main import app

from tests.integration.factories.models.job import JobModelFactory


class TestTrackStreamingHistoryImport:
    @pytest.fixture
    def url(self) -> str:
        return app.url_path_for("track_streaming_history_import")

    async def test__not_authenticated(self, url: str, zip_archive: bytes, async_client: AsyncClient) -> None:
        response = await async_client.post(url, files={"archive": ("export.zip", zip_archive, "application/zip")})

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test__nominal(
        self,
        url: str,
        zip_archive: bytes,
        user: User,
        access_token: str,
        async_client: AsyncClient,
        file_storage: LocalFileStorage,
    ) -> None:
        response = await async_client.post(
            url,
            files={"archive": ("my_spotify_data.zip", zip_archive, "application/zip")},
            data={"min_duration_played": "30", "purge": "true"},
        )

        assert response.status_code == status.HTTP_202_ACCEPTED
        response_data = response.json()
        job_id = response_data["id"]
        assert response.headers["Location"] == app.url_path_for("job_get", job_id=job_id)
        assert response_data["kind"] == "track_history_import"
        assert response_data["status"] == JobStatus.PENDING
        assert response_data["input"] == {"provider": "spotify", "min_ms_played": 30_000, "purge": True}
        assert response_data["result"] is None
        # Stored as is: the worker extracts it
        archive_key = f"history/{job_id}/archive.zip"
        assert await file_storage.get(user_id=user.id, key=archive_key) == zip_archive

    @pytest.mark.parametrize(
        ("file_name", "content_type"),
        [("export.rar", "application/zip"), ("export.zip", "application/json")],
    )
    async def test__not_zip__name_or_type(
        self,
        url: str,
        file_name: str,
        content_type: str,
        zip_archive: bytes,
        user: User,
        access_token: str,
        async_client: AsyncClient,
        file_storage: LocalFileStorage,
    ) -> None:
        response = await async_client.post(url, files={"archive": (file_name, zip_archive, content_type)})

        assert response.status_code == status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
        assert response.json()["detail"] == "The file is not a readable zip archive"
        assert await file_storage.list_keys(user_id=user.id, prefix="history") == []

    @pytest.mark.parametrize(
        "content",
        [b'{"not": "a zip"}', b"PK\x03\x04 then anything but a zip"],
        ids=["signature", "unreadable"],
    )
    async def test__not_zip__content(
        self,
        url: str,
        content: bytes,
        user: User,
        access_token: str,
        async_client: AsyncClient,
    ) -> None:
        # Named and typed as a zip, which proves nothing
        response = await async_client.post(url, files={"archive": ("export.zip", content, "application/zip")})

        assert response.status_code == status.HTTP_415_UNSUPPORTED_MEDIA_TYPE

    async def test__too_large(
        self,
        url: str,
        user: User,
        access_token: str,
        async_client: AsyncClient,
        file_storage: LocalFileStorage,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(app_settings, "HISTORY_UPLOAD_ARCHIVE_MAX_SIZE_MB", 1)
        content = b"PK\x03\x04" + b"\x00" * 1024 * 1024

        response = await async_client.post(url, files={"archive": ("export.zip", content, "application/zip")})

        assert response.status_code == status.HTTP_413_CONTENT_TOO_LARGE
        assert await file_storage.list_keys(user_id=user.id, prefix="history") == []

    async def test__already_active(
        self,
        url: str,
        zip_archive: bytes,
        user: User,
        access_token: str,
        async_client: AsyncClient,
    ) -> None:
        await JobModelFactory.create_async(user_id=user.id, status=JobStatus.PENDING)

        response = await async_client.post(url, files={"archive": ("export.zip", zip_archive, "application/zip")})

        assert response.status_code == status.HTTP_409_CONFLICT
