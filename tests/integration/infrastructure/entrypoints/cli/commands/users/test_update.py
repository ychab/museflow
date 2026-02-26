from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import pytest

from museflow.domain.entities.user import User
from museflow.domain.ports.security import PasswordHasherPort
from museflow.domain.schemas.user import UserUpdate
from museflow.infrastructure.adapters.database.models import User as UserModel
from museflow.infrastructure.entrypoints.cli.commands.users import user_update_logic


class TestUserUpdateLogic:
    async def test__nominal(
        self,
        async_session_db: AsyncSession,
        user: User,
        password_hasher: PasswordHasherPort,
        capsys: pytest.CaptureFixture,
    ) -> None:
        email = "new@museflow.com"
        password = "new-password"

        await user_update_logic(user.id, user_data=UserUpdate(email=email, password=password))

        stmt = select(UserModel).where(UserModel.id == user.id)
        result = await async_session_db.execute(stmt)
        user_db = result.scalar_one()

        assert user_db is not None
        assert user_db.email == email
        assert user_db.is_active is True
        assert password_hasher.verify(password, user_db.hashed_password) is True
