from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.application.use_cases.user_delete import user_delete
from museflow.domain.entities.user import User
from museflow.infrastructure.adapters.database.models import User as UserModel


class TestUserDeleteUseCase:
    async def test__nominal(self, async_session_db: AsyncSession, user: User, uow: UnitOfWorkPort) -> None:
        await user_delete(user_id=user.id, uow=uow)

        result = await async_session_db.execute(select(UserModel).where(UserModel.id == user.id))
        assert result.scalar_one_or_none() is None
