from museflow.domain.entities.user import User
from museflow.infrastructure.entrypoints.cli.commands.taste.export import taste_export_logic

from tests.integration.factories.models.taste import TasteProfileModelFactory
from tests.integration.factories.models.user import UserModelFactory


class TestTasteExportLogic:
    async def test__nominal(self, user: User) -> None:
        await TasteProfileModelFactory.create_async(user_id=user.id, name="my-profile")
        await TasteProfileModelFactory.create_async(user_id=user.id, name="other-profile")

        result = await taste_export_logic(email=user.email, name="my-profile")

        assert [profile.name for profile in result] == ["my-profile"]
        assert result[0].user_id == user.id

    async def test__all_profiles(self, user: User) -> None:
        other_user_db = await UserModelFactory.create_async()
        await TasteProfileModelFactory.create_async(user_id=user.id, name="profile-a")
        await TasteProfileModelFactory.create_async(user_id=user.id, name="profile-b")
        await TasteProfileModelFactory.create_async(user_id=other_user_db.id, name="foreign-profile")

        result = await taste_export_logic(email=user.email)

        assert sorted(profile.name for profile in result) == ["profile-a", "profile-b"]
