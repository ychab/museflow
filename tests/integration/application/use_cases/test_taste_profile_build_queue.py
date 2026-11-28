from datetime import UTC
from datetime import datetime
from datetime import timedelta

from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import pytest

from museflow.application.inputs.taste import BuildTasteProfileJobInput
from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.application.use_cases.taste_profile_build_queue import queue_taste_profile_build
from museflow.domain.entities.user import User
from museflow.domain.enums import JobKind
from museflow.domain.enums import JobStatus
from museflow.domain.enums import TasteProfileStatus
from museflow.domain.exceptions import JobAlreadyActiveError
from museflow.domain.exceptions import TasteProfileAlreadyExistsError
from museflow.domain.exceptions import TasteProfileBuildInProgressError
from museflow.infrastructure.adapters.database.models import JobModel

from tests.integration.factories.models.job import JobModelFactory
from tests.integration.factories.models.taste import TasteProfileBuildModelFactory
from tests.integration.factories.models.taste import TasteProfileModelFactory


class TestQueueTasteProfileBuild:
    @pytest.fixture
    def job_in(self) -> BuildTasteProfileJobInput:
        return BuildTasteProfileJobInput(title="Soirées d'hiver")

    async def test__nominal(self, user: User, job_in: BuildTasteProfileJobInput, uow: UnitOfWorkPort) -> None:
        job = await queue_taste_profile_build(user=user, job_in=job_in, uow=uow)

        assert job.kind == JobKind.TASTE_BUILD
        assert job.status == JobStatus.PENDING
        assert job.input == {"title": "Soirées d'hiver", "name": "soirees-d-hiver", "rated_only": False}
        async with uow:
            assert await uow.jobs.get(user.id, job.id) == job

    async def test__building__queued_to_resume(
        self,
        user: User,
        job_in: BuildTasteProfileJobInput,
        uow: UnitOfWorkPort,
    ) -> None:
        # A paused build: its lease released, its profile partial
        await TasteProfileModelFactory.create_async(
            user_id=user.id,
            name=job_in.name,
            status=TasteProfileStatus.BUILDING,
        )

        job = await queue_taste_profile_build(user=user, job_in=job_in, uow=uow)

        assert job.input["name"] == job_in.name

    async def test__finished(
        self,
        user: User,
        job_in: BuildTasteProfileJobInput,
        uow: UnitOfWorkPort,
        async_session_db: AsyncSession,
    ) -> None:
        await TasteProfileModelFactory.create_async(user_id=user.id, name=job_in.name)

        with pytest.raises(TasteProfileAlreadyExistsError):
            await queue_taste_profile_build(user=user, job_in=job_in, uow=uow)

        assert (await async_session_db.execute(select(func.count()).select_from(JobModel))).scalar_one() == 0

    async def test__held_by_a_build(
        self,
        user: User,
        job_in: BuildTasteProfileJobInput,
        uow: UnitOfWorkPort,
        async_session_db: AsyncSession,
    ) -> None:
        await TasteProfileBuildModelFactory.create_async(
            user_id=user.id,
            name=job_in.name,
            lease_until=datetime.now(UTC) + timedelta(minutes=10),
        )

        with pytest.raises(TasteProfileBuildInProgressError):
            await queue_taste_profile_build(user=user, job_in=job_in, uow=uow)

        assert (await async_session_db.execute(select(func.count()).select_from(JobModel))).scalar_one() == 0

    async def test__already_active__other_profile(
        self,
        user: User,
        job_in: BuildTasteProfileJobInput,
        uow: UnitOfWorkPort,
    ) -> None:
        # One build per user at a time, whatever its profile
        await JobModelFactory.create_async(
            user_id=user.id,
            kind=JobKind.TASTE_BUILD,
            status=JobStatus.RUNNING,
            input=BuildTasteProfileJobInput(title="Other").model_dump(mode="json"),
        )

        with pytest.raises(JobAlreadyActiveError):
            await queue_taste_profile_build(user=user, job_in=job_in, uow=uow)
