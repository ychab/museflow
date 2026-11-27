import uuid
from pathlib import Path
from typing import Final

from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import pytest

from museflow.application.inputs.history import ImportStreamingHistoryJobInput
from museflow.domain.enums import JobStatus
from museflow.domain.enums import MusicProvider
from museflow.infrastructure.adapters.database.models import JobModel
from museflow.infrastructure.adapters.database.models import TrackModel
from museflow.infrastructure.adapters.storage.local import LocalFileStorage
from museflow.infrastructure.entrypoints.worker.tasks.track.history_import import track_history_import_task

from tests import ASSETS_DIR
from tests.integration.factories.models.job import JobModelFactory
from tests.integration.factories.models.user import UserModelFactory
from tests.integration.infrastructure.entrypoints.worker.celery_worker import CeleryWorker
from tests.integration.infrastructure.entrypoints.worker.conftest import JobWaiter

SAMPLES_DIR: Final[Path] = ASSETS_DIR / "history" / "spotify" / "samples"
SAMPLE_2017: Final[bytes] = (SAMPLES_DIR / "Streaming_History_Audio_2017_2018.json").read_bytes()
SAMPLE_2023: Final[bytes] = (SAMPLES_DIR / "Streaming_History_Audio_2023_2024.json").read_bytes()


class TestTrackHistoryImportTask:
    async def test__nominal(
        self,
        worker: CeleryWorker,
        zip_archive: bytes,
        file_storage: LocalFileStorage,
        async_session_trans: AsyncSession,
        wait_for_job: JobWaiter,
    ) -> None:
        job_db = await self._queue(async_session_trans, file_storage, zip_archive)

        job_db = await wait_for_job(job_db.id, JobStatus.DONE)

        # The sample files, nested in a folder of the archive: 6 plays read, 2 too short
        assert job_db.result == {
            "items_read": 6,
            "items_skipped_no_timestamp": 0,
            "items_skipped_short_play": 2,
            "items_skipped_no_track_id": 0,
            "unique_track_ids": 4,
            "tracks_already_known": 0,
            "plays_total": 4,
            "plays_created": 4,
            "tracks_created": 4,
            "tracks_purged": 0,
        }
        assert await self._count_tracks(async_session_trans, job_db.user_id) == 4
        assert await file_storage.list_keys(user_id=job_db.user_id, prefix="history") == []

    @pytest.mark.parametrize(
        "zip_archive",
        [
            {
                "../../../../Streaming_History_Audio_2017_2018.json": SAMPLE_2017,
                "/etc/Streaming_History_Audio_2023_2024.json": SAMPLE_2023,
            }
        ],
        indirect=True,
    )
    async def test__path_traversal__file_name_only(
        self,
        worker: CeleryWorker,
        zip_archive: bytes,
        file_storage_dir: Path,
        file_storage: LocalFileStorage,
        async_session_trans: AsyncSession,
        wait_for_job: JobWaiter,
    ) -> None:
        job_db = await self._queue(async_session_trans, file_storage, zip_archive)

        job_db = await wait_for_job(job_db.id, JobStatus.DONE)

        # Imported under their name alone: nothing written out of the user's storage
        assert job_db.result is not None
        assert job_db.result["tracks_created"] == 4
        assert [path.name for path in file_storage_dir.parent.rglob("Streaming_History_Audio_*")] == []

    @pytest.mark.parametrize(
        "zip_archive",
        [
            {
                "first/Streaming_History_Audio_2017_2018.json": SAMPLE_2017,
                "second/Streaming_History_Audio_2017_2018.json": SAMPLE_2017,
            }
        ],
        indirect=True,
    )
    async def test__same_name__both_kept(
        self,
        worker: CeleryWorker,
        zip_archive: bytes,
        file_storage: LocalFileStorage,
        async_session_trans: AsyncSession,
        wait_for_job: JobWaiter,
    ) -> None:
        job_db = await self._queue(async_session_trans, file_storage, zip_archive)

        job_db = await wait_for_job(job_db.id, JobStatus.DONE)

        # Both files read, their plays saved once
        assert job_db.result is not None
        assert job_db.result["items_read"] == 6
        assert job_db.result["plays_created"] == 2

    @pytest.mark.parametrize(
        "zip_archive",
        # 3 MB of zeros compress to a few KB: over the 1 MB a file of the test worker may extract
        [{"Streaming_History_Audio_bomb.json": b"0" * 3 * 1024 * 1024}],
        indirect=True,
    )
    async def test__zip_bomb__failed(
        self,
        worker: CeleryWorker,
        zip_archive: bytes,
        file_storage: LocalFileStorage,
        async_session_trans: AsyncSession,
        wait_for_job: JobWaiter,
    ) -> None:
        assert len(zip_archive) < 100 * 1024

        job_db = await self._queue(async_session_trans, file_storage, zip_archive)

        job_db = await wait_for_job(job_db.id, JobStatus.FAILED)
        assert job_db.error == "ArchiveTooLargeError"
        assert await self._count_tracks(async_session_trans, job_db.user_id) == 0
        assert await file_storage.list_keys(user_id=job_db.user_id, prefix="history") == []

    @pytest.mark.parametrize("zip_archive", [{"Spotify Account Data/Userdata.json": b"{}"}], indirect=True)
    async def test__no_history_file__failed(
        self,
        worker: CeleryWorker,
        zip_archive: bytes,
        file_storage: LocalFileStorage,
        async_session_trans: AsyncSession,
        wait_for_job: JobWaiter,
    ) -> None:
        job_db = await self._queue(async_session_trans, file_storage, zip_archive)

        job_db = await wait_for_job(job_db.id, JobStatus.FAILED)
        assert job_db.error == "StreamingHistoryFilesNotFoundError"
        assert await file_storage.list_keys(user_id=job_db.user_id, prefix="history") == []

    @staticmethod
    async def _queue(session: AsyncSession, file_storage: LocalFileStorage, archive: bytes) -> JobModel:
        """Stores the archive and records its job, as the API does, then sends the task, as the relay does."""
        user_db = await UserModelFactory.create_async()
        job_in = ImportStreamingHistoryJobInput(
            prefix=f"history/{uuid.uuid4()}",
            provider=MusicProvider.SPOTIFY,
            min_ms_played=30_000,
        )
        await file_storage.put(user_id=user_db.id, key=job_in.archive_key, content=archive)
        job_db = await JobModelFactory.create_async(user_id=user_db.id, input=job_in.model_dump(mode="json"))
        await session.commit()

        track_history_import_task.apply_async(args=(str(job_db.id), str(job_db.user_id)), task_id=str(job_db.id))
        return job_db

    @staticmethod
    async def _count_tracks(session: AsyncSession, user_id: uuid.UUID) -> int:
        statement = select(func.count()).select_from(TrackModel).where(TrackModel.user_id == user_id)
        return (await session.execute(statement)).scalar_one()
