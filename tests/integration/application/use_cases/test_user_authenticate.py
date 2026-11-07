from museflow.application.ports.security import PasswordHasherPort
from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.application.use_cases.user_authenticate import authenticate_user
from museflow.domain.entities.user import User


class TestAuthenticateUserUseCase:
    async def test__authenticate__nominal(
        self,
        uow: UnitOfWorkPort,
        user: User,
        password_hasher: PasswordHasherPort,
    ) -> None:
        user_auth = await authenticate_user(
            email=user.email,
            password="testtest",
            uow=uow,
            password_hasher=password_hasher,
        )
        assert user_auth is not None
        assert user_auth.email == user.email
