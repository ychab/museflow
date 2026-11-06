from museflow.application.ports.repositories.users import UserRepository
from museflow.domain.entities.user import User
from museflow.infrastructure.entrypoints.cli.commands.users.delete import delete_logic


class TestUsersDeleteLogic:
    async def test__nominal(self, user: User, user_repository: UserRepository) -> None:
        await delete_logic(email=user.email)

        assert await user_repository.get_by_id(user.id) is None
