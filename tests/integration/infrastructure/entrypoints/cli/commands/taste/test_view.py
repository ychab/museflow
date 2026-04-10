from museflow.domain.entities.taste import TasteProfile
from museflow.domain.entities.user import User
from museflow.infrastructure.entrypoints.cli.commands.taste.view import view_logic

from tests.integration.factories.models.taste import TasteProfileModelFactory


class TestTasteViewLogic:
    async def test__nominal(self, user: User) -> None:
        taste_profile_db = await TasteProfileModelFactory.create_async(user_id=user.id, name="my-profile")

        result = await view_logic(email=user.email, name=taste_profile_db.name)

        assert isinstance(result, TasteProfile)
        assert result.name == "my-profile"
