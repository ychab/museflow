import uuid

from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import pytest

from museflow.application.inputs.enrich import EnrichTracksJobInput
from museflow.domain.enums import GenreTag
from museflow.domain.enums import JobKind
from museflow.domain.enums import JobStatus
from museflow.domain.enums import MoodTag
from museflow.infrastructure.adapters.database.models import JobModel
from museflow.infrastructure.adapters.database.models import LLMUsageModel
from museflow.infrastructure.entrypoints.worker.main import celery_app
from museflow.infrastructure.entrypoints.worker.tasks.track.enrich import track_enrich_task

from tests.integration.factories.models.job import JobModelFactory
from tests.integration.factories.models.track import TrackModelFactory
from tests.integration.factories.models.user import UserModelFactory
from tests.integration.infrastructure.entrypoints.worker.celery_worker import CeleryWorker
from tests.integration.infrastructure.entrypoints.worker.conftest import JobWaiter


@pytest.mark.wiremock("openrouter")
class TestTrackEnrichTask:
    async def test__nominal(
        self,
        worker: CeleryWorker,
        async_session_trans: AsyncSession,
        wait_for_job: JobWaiter,
    ) -> None:
        user_db = await UserModelFactory.create_async()
        track_db = await TrackModelFactory.create_async(user_id=user_db.id)
        job_db = await self._create_job(async_session_trans, user_db.id)

        track_enrich_task.apply_async(args=(str(job_db.id), str(job_db.user_id)), task_id=str(job_db.id))

        job_db = await wait_for_job(job_db.id, JobStatus.DONE)
        assert job_db.result == {"enriched_count": 1, "error_count": 0, "not_found_count": 0}
        await async_session_trans.refresh(track_db)
        assert track_db.genres == [GenreTag.FOLK, GenreTag.INDIE_FOLK]
        assert await self._llm_calls(async_session_trans, job_db.user_id) == 1
        assert f"Job {job_db.id}: LLM cost $0.0002" in worker.logs

    async def test__retried__resumed(
        self,
        worker: CeleryWorker,
        async_session_trans: AsyncSession,
        wait_for_job: JobWaiter,
    ) -> None:
        # Its first try died after enriching the first track: the job is left running
        user_db = await UserModelFactory.create_async()
        done_db = await TrackModelFactory.create_async(
            user_id=user_db.id,
            genres=[GenreTag.JAZZ],
            moods=[MoodTag.CHILL],
            locales=[],
        )
        left_db = await TrackModelFactory.create_async(user_id=user_db.id)
        job_db = await self._create_job(async_session_trans, user_db.id, status=JobStatus.RUNNING)

        # The retry of a lost process, as Celery publishes it
        celery_app.send_task(
            track_enrich_task.name,
            args=(str(job_db.id), str(job_db.user_id)),
            task_id=str(job_db.id),
            retries=1,
        )

        job_db = await wait_for_job(job_db.id, JobStatus.DONE)
        assert job_db.result is not None
        assert job_db.result["enriched_count"] == 1
        await async_session_trans.refresh(done_db)
        await async_session_trans.refresh(left_db)
        assert done_db.genres == [GenreTag.JAZZ]
        assert left_db.genres == [GenreTag.FOLK, GenreTag.INDIE_FOLK]
        # One batch paid: the track the first try enriched was not sent again
        assert await self._llm_calls(async_session_trans, job_db.user_id) == 1

    @staticmethod
    async def _create_job(
        session: AsyncSession, user_id: uuid.UUID, status: JobStatus = JobStatus.PENDING
    ) -> JobModel:
        """Records the job, as the API does; the test sends the task, as the relay does."""
        job_db = await JobModelFactory.create_async(
            user_id=user_id,
            kind=JobKind.TRACK_ENRICH,
            status=status,
            input=EnrichTracksJobInput().model_dump(mode="json"),
        )
        await session.commit()
        return job_db

    @staticmethod
    async def _llm_calls(session: AsyncSession, user_id: uuid.UUID) -> int:
        statement = select(func.sum(LLMUsageModel.calls)).where(LLMUsageModel.user_id == user_id)
        return (await session.execute(statement)).scalar_one()
