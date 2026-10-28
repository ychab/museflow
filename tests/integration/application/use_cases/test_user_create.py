from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import pytest

from museflow.application.inputs.user import UserCreateInput
from museflow.application.ports.security import PasswordHasherPort
from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.application.use_cases.user_create import user_create
from museflow.infrastructure.adapters.database.models import User as UserModel

from tests.unit.factories.inputs.user import UserCreateInputFactory


class TestUserCreateUseCase:
    @pytest.fixture
    def user_create_data(self) -> UserCreateInput:
        return UserCreateInputFactory.build(password="testtest")

    async def test__nominal(
        self,
        async_session_db: AsyncSession,
        user_create_data: UserCreateInput,
        uow: UnitOfWorkPort,
        password_hasher: PasswordHasherPort,
    ) -> None:
        user = await user_create(user_create_data, uow, password_hasher)

        stmt = select(UserModel).where(UserModel.id == user.id)
        result = await async_session_db.execute(stmt)
        user_db = result.scalar_one_or_none()
        assert user_db
        assert user_db.email == user.email
        assert password_hasher.verify(user_create_data.password, user_db.hashed_password)
