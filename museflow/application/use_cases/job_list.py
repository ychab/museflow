from museflow.application.outputs.pagination import Page
from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.domain.entities.job import Job
from museflow.domain.entities.user import User


async def get_jobs(user: User, uow: UnitOfWorkPort, limit: int | None = None, offset: int = 0) -> Page[Job]:
    async with uow:
        jobs = await uow.jobs.get_list(user.id, limit=limit, offset=offset)
        total = await uow.jobs.count(user.id)

    return Page(items=jobs, total=total, limit=limit, offset=offset)
