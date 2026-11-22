from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.application.use_cases.job_get import get_job
from museflow.domain.entities.user import User

from tests.integration.factories.models.job import JobModelFactory


class TestGetJobUseCase:
    async def test__nominal(self, uow: UnitOfWorkPort, user: User) -> None:
        job_db = await JobModelFactory.create_async(user_id=user.id)

        job = await get_job(user=user, job_id=job_db.id, uow=uow)

        assert job.id == job_db.id
