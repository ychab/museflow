import uuid

from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.domain.entities.job import Job
from museflow.domain.entities.user import User
from museflow.domain.exceptions import JobNotFoundError


async def get_job(user: User, job_id: uuid.UUID, uow: UnitOfWorkPort) -> Job:
    async with uow:
        job = await uow.jobs.get(user.id, job_id)

    if job is None:
        raise JobNotFoundError()

    return job
