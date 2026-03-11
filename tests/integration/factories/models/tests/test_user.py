from pydantic import EmailStr
from pydantic import TypeAdapter

from museflow.application.ports.security import PasswordHasherPort
from museflow.domain.entities.user import User

email_adapter = TypeAdapter(EmailStr)


class TestUserModelFactory:
    def test__field__email(self, user: User) -> None:
        assert email_adapter.validate_python(user.email)

    def test__field__hashed_password(self, user: User, password_hasher: PasswordHasherPort) -> None:
        assert password_hasher.verify("testtest", user.hashed_password)
