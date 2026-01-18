from unittest import mock

from spotifagent.application.use_cases.user_authenticate import user_authenticate
from spotifagent.domain.entities.users import User
from spotifagent.domain.ports.security import PasswordHasherPort


class TestUserAuthenticateUseCase:
    async def test_authenticate__nominal(
        self,
        user: User,
        user_repository: mock.Mock,
        password_hasher: PasswordHasherPort,
    ) -> None:
        user_auth = await user_authenticate(
            email=user.email,
            password="testtest",
            user_repository=user_repository,
            password_hasher=password_hasher,
        )
        assert user_auth is not None
        assert user_auth.email == user.email
