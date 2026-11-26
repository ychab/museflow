import pytest

from museflow.application.ports.archive import ArchivePort
from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.application.use_cases.track_history_import_queue import queue_history_import
from museflow.domain.entities.user import User
from museflow.domain.enums import JobKind
from museflow.domain.enums import JobStatus
from museflow.domain.enums import MusicProvider
from museflow.domain.exceptions import ArchiveInvalidError
from museflow.domain.exceptions import JobAlreadyActiveError
from museflow.infrastructure.adapters.storage.local import LocalFileStorage

from tests.integration.factories.models.job import JobModelFactory


class TestQueueHistoryImport:
    async def test__nominal(
        self,
        user: User,
        zip_archive: bytes,
        uow: UnitOfWorkPort,
        file_storage: LocalFileStorage,
        archive_reader: ArchivePort,
    ) -> None:
        job = await queue_history_import(
            user=user,
            archive=zip_archive,
            provider=MusicProvider.SPOTIFY,
            min_ms_played=30_000,
            purge=True,
            uow=uow,
            file_storage=file_storage,
            archive_reader=archive_reader,
        )

        assert job.kind == JobKind.TRACK_HISTORY_IMPORT
        assert job.status == JobStatus.PENDING
        assert job.input == {
            "prefix": f"history/{job.id}",
            "provider": "spotify",
            "min_ms_played": 30_000,
            "purge": True,
        }
        archive_key = f"history/{job.id}/archive.zip"
        assert await file_storage.list_keys(user_id=user.id, prefix=f"history/{job.id}") == [archive_key]
        assert await file_storage.get(user_id=user.id, key=archive_key) == zip_archive

    async def test__already_active__archive_deleted(
        self,
        user: User,
        zip_archive: bytes,
        uow: UnitOfWorkPort,
        file_storage: LocalFileStorage,
        archive_reader: ArchivePort,
    ) -> None:
        await JobModelFactory.create_async(user_id=user.id, status=JobStatus.RUNNING)

        with pytest.raises(JobAlreadyActiveError):
            await queue_history_import(
                user=user,
                archive=zip_archive,
                provider=MusicProvider.SPOTIFY,
                min_ms_played=30_000,
                purge=False,
                uow=uow,
                file_storage=file_storage,
                archive_reader=archive_reader,
            )

        assert await file_storage.list_keys(user_id=user.id, prefix="history") == []

    async def test__archive__invalid__nothing_stored(
        self,
        user: User,
        uow: UnitOfWorkPort,
        file_storage: LocalFileStorage,
        archive_reader: ArchivePort,
    ) -> None:
        with pytest.raises(ArchiveInvalidError, match="Not a zip archive"):
            await queue_history_import(
                user=user,
                archive=b"not a zip",
                provider=MusicProvider.SPOTIFY,
                min_ms_played=30_000,
                purge=False,
                uow=uow,
                file_storage=file_storage,
                archive_reader=archive_reader,
            )

        assert await file_storage.list_keys(user_id=user.id, prefix="history") == []
