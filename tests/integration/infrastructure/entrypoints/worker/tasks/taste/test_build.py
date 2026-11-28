import uuid
from datetime import UTC
from datetime import datetime
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import pytest

from museflow.application.inputs.taste import BuildTasteProfileJobInput
from museflow.domain.enums import JobKind
from museflow.domain.enums import JobStatus
from museflow.domain.enums import TasteProfileStatus
from museflow.infrastructure.adapters.database.models import JobModel
from museflow.infrastructure.adapters.database.models import LLMUsageModel
from museflow.infrastructure.adapters.database.models import TasteProfileBuildModel
from museflow.infrastructure.adapters.database.models import TasteProfileModel
from museflow.infrastructure.entrypoints.worker.main import celery_app
from museflow.infrastructure.entrypoints.worker.tasks.taste.build import taste_build_task

from tests.integration.factories.models.job import JobModelFactory
from tests.integration.factories.models.taste import TasteProfileBuildModelFactory
from tests.integration.factories.models.taste import TasteProfileDataFactory
from tests.integration.factories.models.taste import TasteProfileModelFactory
from tests.integration.factories.models.track import TrackModelFactory
from tests.integration.factories.models.user import UserModelFactory
from tests.integration.infrastructure.entrypoints.worker.celery_worker import CeleryWorker
from tests.integration.infrastructure.entrypoints.worker.conftest import JobWaiter
from tests.integration.utils.wiremock import WireMockContext


@pytest.mark.wiremock("openrouter")
class TestTasteBuildTask:
    async def test__nominal(
        self,
        worker: CeleryWorker,
        async_session_trans: AsyncSession,
        wait_for_job: JobWaiter,
    ) -> None:
        user_id = (await UserModelFactory.create_async()).id
        await TrackModelFactory.create_batch_async(size=3, user_id=user_id, played_count=1)
        job_db = await self._create_job(async_session_trans, user_id)

        taste_build_task.apply_async(args=(str(job_db.id), str(job_db.user_id)), task_id=str(job_db.id))

        job_db = await wait_for_job(job_db.id, JobStatus.DONE)
        assert job_db.result == {"name": "winter", "tracks_count": 3}
        profile_db = await self._get_profile(async_session_trans, user_id)
        assert (profile_db.title, profile_db.status) == ("Winter", TasteProfileStatus.FINISHED)
        # One period, then the reflection
        assert await self._llm_steps(async_session_trans, user_id) == {"profiler segment", "profiler reflect"}
        assert not await self._lease_held(async_session_trans, user_id)
        assert f"Job {job_db.id}: LLM cost $" in worker.logs

    async def test__paused__failed(
        self,
        openrouter_wiremock: WireMockContext,
        worker: CeleryWorker,
        async_session_trans: AsyncSession,
        wait_for_job: JobWaiter,
    ) -> None:
        # The segment answered, the reflection rate-limited past the retries of the adapter
        openrouter_wiremock.create_mapping(
            method="POST",
            url_path="/chat/completions",
            status=429,
            json_body={"error": {"message": "Rate limit exceeded", "code": 429}},
            scenario_name="build paused",
            required_state="reflect",
        )
        openrouter_wiremock.create_mapping(
            method="POST",
            url_path="/chat/completions",
            status=200,
            body_file_name="chat_completions_profiler_segment.json",
            scenario_name="build paused",
            required_state="Started",
            new_state="reflect",
        )
        user_id = (await UserModelFactory.create_async()).id
        await TrackModelFactory.create_batch_async(size=3, user_id=user_id, played_count=1)
        job_db = await self._create_job(async_session_trans, user_id)

        taste_build_task.apply_async(args=(str(job_db.id), str(job_db.user_id)), task_id=str(job_db.id))

        job_db = await wait_for_job(job_db.id, JobStatus.FAILED)
        assert job_db.error == "TasteProfileBuildPausedError"
        profile_db = await self._get_profile(async_session_trans, user_id)
        assert (profile_db.status, profile_db.checkpoint_batch_index) == (TasteProfileStatus.BUILDING, 1)
        assert not await self._lease_held(async_session_trans, user_id)
        # The period stays paid and saved: the same request queues a job that resumes after it
        assert await self._llm_steps(async_session_trans, user_id) == {"profiler segment"}

    async def test__redelivered__lease_of_its_dead_try__taken_over(
        self,
        worker: CeleryWorker,
        async_session_trans: AsyncSession,
        wait_for_job: JobWaiter,
    ) -> None:
        # Its first try died after the only period, its lease still unexpired: the job is left running
        user_id = (await UserModelFactory.create_async()).id
        await TrackModelFactory.create_batch_async(size=3, user_id=user_id, played_count=1)
        job_db = await self._create_job(async_session_trans, user_id, status=JobStatus.RUNNING)
        await TasteProfileModelFactory.create_async(
            user_id=user_id,
            name="winter",
            status=TasteProfileStatus.BUILDING,
            checkpoint_profile=TasteProfileDataFactory.build(),
            checkpoint_batch_index=1,
        )
        await TasteProfileBuildModelFactory.create_async(
            user_id=user_id,
            name="winter",
            job_id=job_db.id,
            lease_until=datetime.now(UTC) + timedelta(minutes=10),
        )
        await async_session_trans.commit()

        # The retry of a lost process, as Celery publishes it
        celery_app.send_task(
            taste_build_task.name,
            args=(str(job_db.id), str(job_db.user_id)),
            task_id=str(job_db.id),
            retries=1,
        )

        job_db = await wait_for_job(job_db.id, JobStatus.DONE)
        assert job_db.result == {"name": "winter", "tracks_count": 3}
        profile_db = await self._get_profile(async_session_trans, user_id)
        assert profile_db.status == TasteProfileStatus.FINISHED
        # Resumed after the period its dead try saved
        assert await self._llm_steps(async_session_trans, user_id) == {"profiler reflect"}
        assert not await self._lease_held(async_session_trans, user_id)

    async def test__redelivered__finished__done_without_build(
        self,
        worker: CeleryWorker,
        async_session_trans: AsyncSession,
        wait_for_job: JobWaiter,
    ) -> None:
        # Its first try died once the profile was saved, before the job was done
        user_id = (await UserModelFactory.create_async()).id
        job_db = await self._create_job(async_session_trans, user_id, status=JobStatus.RUNNING)
        await TasteProfileModelFactory.create_async(user_id=user_id, name="winter", tracks_count=120)
        await async_session_trans.commit()

        celery_app.send_task(
            taste_build_task.name,
            args=(str(job_db.id), str(job_db.user_id)),
            task_id=str(job_db.id),
            retries=1,
        )

        job_db = await wait_for_job(job_db.id, JobStatus.DONE)
        assert job_db.result == {"name": "winter", "tracks_count": 120}
        assert await self._llm_steps(async_session_trans, user_id) == set()
        assert not await self._lease_held(async_session_trans, user_id)

    @staticmethod
    async def _create_job(
        session: AsyncSession,
        user_id: uuid.UUID,
        status: JobStatus = JobStatus.PENDING,
    ) -> JobModel:
        """Records the job, as the API does; the test sends the task, as the relay does."""
        job_db = await JobModelFactory.create_async(
            user_id=user_id,
            kind=JobKind.TASTE_BUILD,
            status=status,
            input=BuildTasteProfileJobInput(title="Winter").model_dump(mode="json"),
        )
        await session.commit()
        return job_db

    @staticmethod
    async def _get_profile(session: AsyncSession, user_id: uuid.UUID) -> TasteProfileModel:
        # The worker wrote the row: read it again, not from the identity map
        statement = (
            select(TasteProfileModel)
            .where(TasteProfileModel.user_id == user_id)
            .execution_options(populate_existing=True)
        )
        return (await session.execute(statement)).scalar_one()

    @staticmethod
    async def _llm_steps(session: AsyncSession, user_id: uuid.UUID) -> set[str]:
        statement = select(LLMUsageModel.step).where(LLMUsageModel.user_id == user_id)
        return set((await session.execute(statement)).scalars())

    @staticmethod
    async def _lease_held(session: AsyncSession, user_id: uuid.UUID) -> bool:
        statement = select(TasteProfileBuildModel).where(TasteProfileBuildModel.user_id == user_id)
        return (await session.execute(statement)).first() is not None
