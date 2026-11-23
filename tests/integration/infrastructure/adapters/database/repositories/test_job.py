import asyncio
import uuid
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from typing import Final

from sqlalchemy import select
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import async_sessionmaker

import pytest

from museflow.application.ports.repositories.job import JobRepository
from museflow.domain.entities.job import Job
from museflow.domain.entities.user import User
from museflow.domain.enums import JobKind
from museflow.domain.enums import JobStatus
from museflow.domain.exceptions import JobAlreadyActiveError
from museflow.infrastructure.adapters.database.models import JobModel
from museflow.infrastructure.adapters.database.repositories.job import JobSQLRepository

from tests.integration.factories.models.job import JobModelFactory
from tests.integration.factories.models.user import UserModelFactory

NOW: Final[datetime] = datetime(2026, 1, 1, tzinfo=UTC)


class TestJobSQLRepository:
    @pytest.fixture
    def job_repository(self, async_session_db: AsyncSession) -> JobRepository:
        return JobSQLRepository(async_session_db)

    @pytest.fixture
    async def job_db(self, request: pytest.FixtureRequest, user: User) -> JobModel:
        return await JobModelFactory.create_async(user_id=user.id, **getattr(request, "param", {}))

    async def _create_job(self, async_session_db: AsyncSession, created_at: datetime, **kwargs: object) -> JobModel:
        # The database sets the creation time
        job_db = await JobModelFactory.create_async(**kwargs)
        await async_session_db.execute(update(JobModel).where(JobModel.id == job_db.id).values(created_at=created_at))
        return job_db

    async def _get_job(self, async_session_db: AsyncSession, job_id: uuid.UUID) -> JobModel:
        job_db = (await async_session_db.execute(select(JobModel).where(JobModel.id == job_id))).scalar_one()
        await async_session_db.refresh(job_db)
        return job_db

    async def test__create__nominal(
        self,
        async_session_db: AsyncSession,
        user: User,
        job_repository: JobRepository,
    ) -> None:
        job_in = Job(user_id=user.id, kind=JobKind.TRACK_HISTORY_IMPORT, input={"chunk_size": 500})

        job = await job_repository.create(job_in)

        assert job.id == job_in.id
        assert job.status == JobStatus.PENDING
        assert job.input == {"chunk_size": 500}
        job_db = await self._get_job(async_session_db, job.id)
        assert job_db.published_at is None

    @pytest.mark.parametrize("job_db", [{"status": JobStatus.PENDING}, {"status": JobStatus.RUNNING}], indirect=True)
    async def test__create__active__conflict(
        self,
        user: User,
        job_db: JobModel,
        job_repository: JobRepository,
    ) -> None:
        with pytest.raises(JobAlreadyActiveError):
            await job_repository.create(Job(user_id=user.id, kind=job_db.kind))

    @pytest.mark.parametrize("job_db", [{"status": JobStatus.DONE}, {"status": JobStatus.FAILED}], indirect=True)
    async def test__create__ended__new_one(
        self,
        user: User,
        job_db: JobModel,
        job_repository: JobRepository,
    ) -> None:
        job = await job_repository.create(Job(user_id=user.id, kind=job_db.kind))

        assert job.id != job_db.id

    async def test__create__other_user__new_one(self, job_db: JobModel, job_repository: JobRepository) -> None:
        other_user = await UserModelFactory.create_async()

        job = await job_repository.create(Job(user_id=other_user.id, kind=job_db.kind))

        assert job.user_id == other_user.id

    async def test__get__nominal(self, user: User, job_db: JobModel, job_repository: JobRepository) -> None:
        job = await job_repository.get(user.id, job_db.id)

        assert job is not None
        assert job.id == job_db.id

    async def test__get__other_user(self, job_db: JobModel, job_repository: JobRepository) -> None:
        assert await job_repository.get(uuid.uuid4(), job_db.id) is None

    async def test__get_list__paged(
        self,
        async_session_db: AsyncSession,
        user: User,
        job_repository: JobRepository,
    ) -> None:
        jobs_db = [
            await self._create_job(
                async_session_db, NOW + timedelta(days=days), user_id=user.id, status=JobStatus.DONE
            )
            for days in (0, 2, 1)
        ]
        await JobModelFactory.create_async()

        jobs = await job_repository.get_list(user.id, limit=2, offset=0)
        total = await job_repository.count(user.id)

        assert [job.id for job in jobs] == [jobs_db[1].id, jobs_db[2].id]
        assert total == 3

    async def test__get_unpublished__oldest_first(
        self,
        async_session_db: AsyncSession,
        job_repository: JobRepository,
    ) -> None:
        newer_db = await self._create_job(async_session_db, NOW + timedelta(days=1))
        older_db = await self._create_job(async_session_db, NOW)
        await JobModelFactory.create_async(published_at=NOW)

        jobs = await job_repository.get_unpublished(limit=10)

        assert [job.id for job in jobs] == [older_db.id, newer_db.id]

    async def test__mark_published__nominal(
        self,
        async_session_db: AsyncSession,
        job_db: JobModel,
        job_repository: JobRepository,
    ) -> None:
        await job_repository.mark_published([job_db.id])

        job_db = await self._get_job(async_session_db, job_db.id)
        assert job_db.published_at is not None
        assert await job_repository.get_unpublished(limit=10) == []

    async def test__start__pending(self, user: User, job_db: JobModel, job_repository: JobRepository) -> None:
        job = await job_repository.start(user.id, job_db.id, resumed=False)

        assert job is not None
        assert job.status == JobStatus.RUNNING
        assert job.started_at is not None

    @pytest.mark.parametrize(
        "job_db",
        [{"status": JobStatus.RUNNING, "started_at": NOW}],
        indirect=True,
    )
    async def test__start__running__resumed(
        self,
        user: User,
        job_db: JobModel,
        job_repository: JobRepository,
    ) -> None:
        job = await job_repository.start(user.id, job_db.id, resumed=True)

        assert job is not None
        assert job.status == JobStatus.RUNNING
        assert job.started_at == job_db.started_at

    @pytest.mark.parametrize("job_db", [{"status": JobStatus.RUNNING}], indirect=True)
    async def test__start__running__duplicate(
        self,
        user: User,
        job_db: JobModel,
        job_repository: JobRepository,
    ) -> None:
        assert await job_repository.start(user.id, job_db.id, resumed=False) is None

    @pytest.mark.parametrize("resumed", [False, True])
    @pytest.mark.parametrize("job_db", [{"status": JobStatus.DONE}, {"status": JobStatus.FAILED}], indirect=True)
    async def test__start__ended(
        self,
        user: User,
        job_db: JobModel,
        job_repository: JobRepository,
        resumed: bool,
    ) -> None:
        assert await job_repository.start(user.id, job_db.id, resumed=resumed) is None

    async def test__start__other_user(self, job_db: JobModel, job_repository: JobRepository) -> None:
        assert await job_repository.start(uuid.uuid4(), job_db.id, resumed=False) is None

    async def test__start__concurrent__one_wins(
        self,
        async_session_trans: AsyncSession,
        async_session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        job_db = await JobModelFactory.create_async()
        await async_session_trans.commit()

        async def start() -> Job | None:
            async with async_session_factory() as session, session.begin():
                return await JobSQLRepository(session).start(job_db.user_id, job_db.id, resumed=False)

        jobs = await asyncio.gather(start(), start())

        assert sorted(job is not None for job in jobs) == [False, True]

    @pytest.mark.parametrize("job_db", [{"status": JobStatus.RUNNING}], indirect=True)
    async def test__finish__running(
        self,
        async_session_db: AsyncSession,
        user: User,
        job_db: JobModel,
        job_repository: JobRepository,
    ) -> None:
        finished = await job_repository.finish(user.id, job_db.id, {"tracks_count": 12})

        assert finished is True

        job_db = await self._get_job(async_session_db, job_db.id)
        assert job_db.status == JobStatus.DONE
        assert job_db.result == {"tracks_count": 12}
        assert job_db.finished_at is not None

    @pytest.mark.parametrize("job_db", [{"status": JobStatus.RUNNING}], indirect=True)
    async def test__fail__running(
        self,
        async_session_db: AsyncSession,
        user: User,
        job_db: JobModel,
        job_repository: JobRepository,
    ) -> None:
        failed = await job_repository.fail(user.id, job_db.id, "StreamingHistoryInvalidFormatError")

        assert failed is True

        job_db = await self._get_job(async_session_db, job_db.id)
        assert job_db.status == JobStatus.FAILED
        assert job_db.error == "StreamingHistoryInvalidFormatError"

    async def test__finish__pending__unchanged(
        self,
        async_session_db: AsyncSession,
        user: User,
        job_db: JobModel,
        job_repository: JobRepository,
    ) -> None:
        finished = await job_repository.finish(user.id, job_db.id, None)

        assert finished is False
        job_db = await self._get_job(async_session_db, job_db.id)
        assert job_db.status == JobStatus.PENDING
