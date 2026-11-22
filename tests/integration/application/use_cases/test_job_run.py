from sqlalchemy.ext.asyncio import AsyncSession

from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.application.use_cases.job_run import RunJobUseCase
from museflow.domain.entities.user import User
from museflow.domain.enums import JobStatus

from tests.integration.factories.models.job import JobModelFactory


class TestRunJobUseCase:
    async def test__start__finish(self, async_session_db: AsyncSession, uow: UnitOfWorkPort, user: User) -> None:
        job_db = await JobModelFactory.create_async(user_id=user.id)
        use_case = RunJobUseCase(user_id=user.id, job_id=job_db.id, uow=uow)

        job = await use_case.start(resumed=False)
        await use_case.finish({"tracks_count": 3})

        assert job is not None
        assert job.status == JobStatus.RUNNING
        await async_session_db.refresh(job_db)
        assert (job_db.status, job_db.result) == (JobStatus.DONE, {"tracks_count": 3})

    async def test__start__fail(self, async_session_db: AsyncSession, uow: UnitOfWorkPort, user: User) -> None:
        job_db = await JobModelFactory.create_async(user_id=user.id)
        use_case = RunJobUseCase(user_id=user.id, job_id=job_db.id, uow=uow)

        await use_case.start(resumed=False)
        await use_case.fail("ValueError")

        await async_session_db.refresh(job_db)
        assert (job_db.status, job_db.error) == (JobStatus.FAILED, "ValueError")
