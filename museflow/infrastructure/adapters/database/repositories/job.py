import uuid
from typing import Any

from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from museflow.application.ports.repositories.job import JobRepository
from museflow.domain.entities.job import Job
from museflow.domain.enums import JobStatus
from museflow.domain.exceptions import JobAlreadyActiveError
from museflow.infrastructure.adapters.database.models import JOB_CHANNEL
from museflow.infrastructure.adapters.database.models import JobModel


class JobSQLRepository(JobRepository):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, job: Job) -> Job:
        job_db = JobModel.from_entity(job)

        # The partial unique index settles a race no check before the insert could see. The savepoint keeps the
        # session usable after the conflict.
        try:
            async with self.session.begin_nested():
                self.session.add(job_db)
        except IntegrityError as e:
            raise JobAlreadyActiveError(f"A {job.kind} job is already pending or running") from e

        # Delivered to the listeners when the transaction commits, never if it rolls back
        await self.session.execute(select(func.pg_notify(JOB_CHANNEL, str(job_db.id))))
        await self.session.refresh(job_db)

        return job_db.to_entity()

    async def get(self, user_id: uuid.UUID, job_id: uuid.UUID) -> Job | None:
        stmt = select(JobModel).where(JobModel.user_id == user_id, JobModel.id == job_id)
        job_db = (await self.session.execute(stmt)).scalar_one_or_none()

        return job_db.to_entity() if job_db else None

    async def get_list(self, user_id: uuid.UUID, limit: int | None = None, offset: int = 0) -> list[Job]:
        stmt = (
            select(JobModel)
            .where(JobModel.user_id == user_id)
            # The ID breaks the ties: pages stay stable between two calls
            .order_by(JobModel.created_at.desc(), JobModel.id)
            .limit(limit)
            .offset(offset)
        )

        result = await self.session.execute(stmt)
        return [row.to_entity() for row in result.scalars()]

    async def count(self, user_id: uuid.UUID) -> int:
        stmt = select(func.count()).select_from(JobModel).where(JobModel.user_id == user_id)
        return (await self.session.execute(stmt)).scalar_one()

    async def get_unpublished(self, limit: int) -> list[Job]:
        stmt = (
            select(JobModel)
            .where(JobModel.published_at.is_(None))
            .order_by(JobModel.created_at, JobModel.id)
            .limit(limit)
        )

        result = await self.session.execute(stmt)
        return [row.to_entity() for row in result.scalars()]

    async def mark_published(self, job_ids: list[uuid.UUID]) -> None:
        stmt = update(JobModel).where(JobModel.id.in_(job_ids)).values(published_at=func.now())
        await self.session.execute(stmt)

    async def start(self, user_id: uuid.UUID, job_id: uuid.UUID, resumed: bool) -> Job | None:
        startable = [JobStatus.PENDING, JobStatus.RUNNING] if resumed else [JobStatus.PENDING]
        # Two workers starting the job at once queue on the row lock; the second one then checks the status again, on
        # the row the first one committed, and updates nothing.
        stmt = (
            update(JobModel)
            .where(JobModel.user_id == user_id, JobModel.id == job_id, JobModel.status.in_(startable))
            .values(
                status=JobStatus.RUNNING,
                # A resumed job keeps the time it first started
                started_at=func.coalesce(JobModel.started_at, func.now()),
            )
            .returning(JobModel)
        )

        job_db = (await self.session.execute(stmt)).scalar_one_or_none()
        return job_db.to_entity() if job_db else None

    async def finish(self, user_id: uuid.UUID, job_id: uuid.UUID, result: dict[str, Any] | None) -> bool:
        return await self._mark_ended(user_id, job_id, status=JobStatus.DONE, result=result)

    async def fail(self, user_id: uuid.UUID, job_id: uuid.UUID, error: str) -> bool:
        return await self._mark_ended(user_id, job_id, status=JobStatus.FAILED, error=error)

    async def _mark_ended(
        self,
        user_id: uuid.UUID,
        job_id: uuid.UUID,
        status: JobStatus,
        result: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> bool:
        stmt = (
            update(JobModel)
            .where(JobModel.user_id == user_id, JobModel.id == job_id, JobModel.status == JobStatus.RUNNING)
            .values(status=status, result=result, error=error, finished_at=func.now())
            .returning(JobModel.id)
        )

        return (await self.session.execute(stmt)).scalar_one_or_none() is not None
