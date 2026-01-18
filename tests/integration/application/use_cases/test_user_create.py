from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import pytest

from spotifagent.application.use_cases.user_create import user_create
from spotifagent.domain.entities.users import UserCreate
from spotifagent.domain.ports.repositories.users import UserRepositoryPort
from spotifagent.domain.ports.security import PasswordHasherPort
from spotifagent.infrastructure.adapters.database.models import User as UserModel

from tests.unit.factories.users import UserCreateFactory


class TestUserCreateUseCase:
    @pytest.fixture
    def user_create_data(self) -> UserCreate:
        return UserCreateFactory.build(password="testtest")

    async def test__nominal(
        self,
        async_session_db: AsyncSession,
        user_create_data: UserCreate,
        user_repository: UserRepositoryPort,
        password_hasher: PasswordHasherPort,
    ) -> None:
        user = await user_create(user_create_data, user_repository, password_hasher)

        stmt = select(UserModel).where(UserModel.id == user.id)
        result = await async_session_db.execute(stmt)
        user_db = result.scalar_one_or_none()
        assert user_db
        assert user_db.email == user.email
        assert password_hasher.verify(user_create_data.password, user_db.hashed_password)
