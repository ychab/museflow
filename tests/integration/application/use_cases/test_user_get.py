from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.application.use_cases.user_get import get_user
from museflow.domain.entities.user import User


class TestGetUserUseCase:
    async def test__nominal(self, uow: UnitOfWorkPort, user: User) -> None:
        found = await get_user(email=user.email, uow=uow)

        assert found.id == user.id
