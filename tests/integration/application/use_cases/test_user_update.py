from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import pytest

from spotifagent.application.use_cases.user_update import user_update
from spotifagent.domain.entities.users import User
from spotifagent.domain.entities.users import UserUpdate
from spotifagent.domain.exceptions import EmailAlreadyExistsException
from spotifagent.domain.ports.repositories.users import UserRepositoryPort
from spotifagent.domain.ports.security import PasswordHasherPort
from spotifagent.infrastructure.adapters.database.models import User as UserModel

from tests.integration.factories.users import UserModelFactory


class TestUserUpdateUseCase:
    async def test_update_email__nominal(
        self,
        async_session_db: AsyncSession,
        user: User,
        user_repository: UserRepositoryPort,
        password_hasher: PasswordHasherPort,
    ) -> None:
        user_update_data = UserUpdate(email="foo@example.com")

        await user_update(
            user=user,
            user_data=user_update_data,
            user_repository=user_repository,
            password_hasher=password_hasher,
        )

        stmt = select(UserModel).where(UserModel.id == user.id)
        result = await async_session_db.execute(stmt)
        user_db = result.scalar_one()

        assert user_db.email == user_update_data.email
        assert user_db.hashed_password == user.hashed_password

    async def test_update_email__same_as_before(
        self,
        async_session_db: AsyncSession,
        user: User,
        user_repository: UserRepositoryPort,
        password_hasher: PasswordHasherPort,
    ) -> None:
        user_update_data = UserUpdate(email=user.email)

        await user_update(
            user=user,
            user_data=user_update_data,
            user_repository=user_repository,
            password_hasher=password_hasher,
        )

        stmt = select(UserModel).where(UserModel.id == user.id)
        result = await async_session_db.execute(stmt)
        user_db = result.scalar_one()

        assert user_db.email == user_update_data.email == user.email

    async def test_update_email__already_exists(
        self,
        user: User,
        user_repository: UserRepositoryPort,
        password_hasher: PasswordHasherPort,
    ) -> None:
        other_user_db = await UserModelFactory.create_async()
        user_update_data = UserUpdate(email=other_user_db.email)

        with pytest.raises(EmailAlreadyExistsException):
            await user_update(
                user=user,
                user_data=user_update_data,
                user_repository=user_repository,
                password_hasher=password_hasher,
            )

    async def test_update_password(
        self,
        async_session_db: AsyncSession,
        user: User,
        user_repository: UserRepositoryPort,
        password_hasher: PasswordHasherPort,
    ) -> None:
        password = "blahblah"
        user_update_data = UserUpdate(password=password)

        user_updated = await user_update(
            user=user,
            user_data=user_update_data,
            user_repository=user_repository,
            password_hasher=password_hasher,
        )

        stmt = select(UserModel).where(UserModel.id == user_updated.id)
        result = await async_session_db.execute(stmt)
        user_db = result.scalar_one()

        assert password_hasher.verify(password, user_db.hashed_password) is True
