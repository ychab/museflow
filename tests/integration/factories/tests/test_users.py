from pydantic import EmailStr
from pydantic import TypeAdapter

from spotifagent.domain.entities.users import User
from spotifagent.domain.ports.security import PasswordHasherPort

from tests.integration.factories.users import UserModelFactory

email_adapter = TypeAdapter(EmailStr)


class TestUserModelFactory:
    def test__field__email(self, user: User) -> None:
        assert email_adapter.validate_python(user.email)

    def test__field__hashed_password(self, user: User, password_hasher: PasswordHasherPort) -> None:
        assert password_hasher.verify("testtest", user.hashed_password)

    async def test__with_spotify_account(self) -> None:
        user_db = await UserModelFactory.create_async(with_spotify_account=True)
        assert user_db.spotify_account is not None
        assert user_db.spotify_account.user_id == user_db.id
