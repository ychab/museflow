from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.application.use_cases.job_list import get_jobs
from museflow.domain.entities.user import User
from museflow.domain.enums import JobStatus

from tests.integration.factories.models.job import JobModelFactory


class TestGetJobsUseCase:
    async def test__nominal(self, uow: UnitOfWorkPort, user: User) -> None:
        for _ in range(3):
            await JobModelFactory.create_async(user_id=user.id, status=JobStatus.DONE)

        page = await get_jobs(user=user, uow=uow, limit=2, offset=0)

        assert len(page.items) == 2
        assert page.total == 3
