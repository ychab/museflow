import uuid
from decimal import Decimal
from typing import Final

from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import anyio
import pytest

from museflow.application.inputs.enrich import EnrichTracksConfigInput
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
from tests.integration.infrastructure.entrypoints.worker.conftest import WAIT_TIMEOUT_SECONDS
from tests.integration.infrastructure.entrypoints.worker.conftest import JobWaiter
from tests.integration.utils.wiremock import WireMockContext

# What the enricher reply of the WireMock fixture costs ($0.0001958), at the precision of the usage column
BATCH_COST: Final[Decimal] = Decimal("0.000196")


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

    async def test__killed__batches_done_recorded(
        self,
        openrouter_wiremock: WireMockContext,
        worker: CeleryWorker,
        async_session_trans: AsyncSession,
    ) -> None:
        # Three batches: the first two answered, the third answered too late, as the worker is killed while it waits
        for required_state, new_state, delay in [
            ("Started", "second", None),
            ("second", "third", None),
            ("third", None, 60_000),
        ]:
            openrouter_wiremock.create_mapping(
                method="POST",
                url_path="/chat/completions",
                status=200,
                body_file_name="chat_completions_enricher.json",
                fixed_delay_milliseconds=delay,
                scenario_name="enrichment killed",
                required_state=required_state,
                new_state=new_state,
            )
        user_db = await UserModelFactory.create_async()
        await TrackModelFactory.create_batch_async(2 * EnrichTracksConfigInput().batch_size + 1, user_id=user_db.id)
        job_db = await self._create_job(async_session_trans, user_db.id)

        track_enrich_task.apply_async(args=(str(job_db.id), str(job_db.user_id)), task_id=str(job_db.id))
        with anyio.fail_after(WAIT_TIMEOUT_SECONDS):
            while await self._llm_calls(async_session_trans, user_db.id) != 2:
                await anyio.sleep(0.2)
        worker.kill()

        # What the two batches cost outlives the process, which never reached the end of its run
        statement = select(LLMUsageModel).where(LLMUsageModel.user_id == user_db.id)
        usage_db = (await async_session_trans.execute(statement)).scalar_one()
        assert (usage_db.calls, usage_db.cost) == (2, 2 * BATCH_COST)
        await async_session_trans.refresh(job_db)
        assert job_db.status == JobStatus.RUNNING

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
        statement = select(func.coalesce(func.sum(LLMUsageModel.calls), 0)).where(LLMUsageModel.user_id == user_id)
        return (await session.execute(statement)).scalar_one()
