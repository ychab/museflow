from museflow.domain.entities.taste import TasteProfile
from museflow.domain.entities.user import User
from museflow.infrastructure.entrypoints.cli.commands.taste.list_ import list_logic

from tests.integration.factories.models.taste import TasteProfileModelFactory


class TestListLogic:
    async def test__nominal(self, user: User) -> None:
        await TasteProfileModelFactory.create_async(user_id=user.id, name="my-profile")

        result = await list_logic(email=user.email)

        assert len(result) == 1
        assert isinstance(result[0], TasteProfile)
        assert result[0].name == "my-profile"
