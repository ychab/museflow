from tests.integration.factories.auth import AuthProviderStateModelFactory
from tests.integration.factories.users import UserModelFactory


class TestAuthProviderStateModelFactory:
    async def test__user__default(self) -> None:
        state_db = await AuthProviderStateModelFactory.create_async()
        assert state_db.user_id is not None

    async def test__user__provided(self) -> None:
        user_db = await UserModelFactory.create_async()
        state_db = await AuthProviderStateModelFactory.create_async(user_id=user_db.id)
        assert state_db.user_id == user_db.id
