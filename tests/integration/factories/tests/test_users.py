from pydantic import EmailStr
from pydantic import TypeAdapter

from museflow.domain.entities.users import User
from museflow.domain.ports.security import PasswordHasherPort

email_adapter = TypeAdapter(EmailStr)


class TestUserModelFactory:
    def test__field__email(self, user: User) -> None:
        assert email_adapter.validate_python(user.email)

    def test__field__hashed_password(self, user: User, password_hasher: PasswordHasherPort) -> None:
        assert password_hasher.verify("testtest", user.hashed_password)
