from museflow.application.ports.repositories.taste import TasteProfileRepository
from museflow.domain.entities.user import User
from museflow.infrastructure.entrypoints.cli.commands.taste.delete import taste_delete_logic

from tests.integration.factories.models.taste import TasteProfileModelFactory


class TestTasteDeleteLogic:
    async def test__nominal(self, user: User, taste_profile_repository: TasteProfileRepository) -> None:
        await TasteProfileModelFactory.create_async(user_id=user.id, name="my-profile")

        await taste_delete_logic(email=user.email, name="my-profile")

        assert await taste_profile_repository.get(user_id=user.id, name="my-profile") is None
