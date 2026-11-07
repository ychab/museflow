from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.application.use_cases.taste_profile_import import import_taste_profile
from museflow.domain.entities.user import User
from museflow.infrastructure.adapters.database.models.taste import TasteProfileModel

from tests.integration.factories.models.taste import TasteProfileModelFactory
from tests.integration.factories.models.user import UserModelFactory


class TestImportTasteProfileUseCase:
    async def test__nominal(self, user: User, uow: UnitOfWorkPort, async_session_db: AsyncSession) -> None:
        taste_profile_db = await TasteProfileModelFactory.create_async(user_id=user.id, name="my-profile")

        result = await import_taste_profile(user_id=user.id, taste_profile=taste_profile_db.to_entity(), uow=uow)

        assert result.name == "my-profile"
        assert result.user_id == user.id

        stmt = select(TasteProfileModel).where(TasteProfileModel.user_id == user.id)
        rows = (await async_session_db.execute(stmt)).scalars().all()
        assert len(rows) == 1

    async def test__other_user__new_id(self, user: User, uow: UnitOfWorkPort, async_session_db: AsyncSession) -> None:
        other_user_db = await UserModelFactory.create_async()
        taste_profile_db = await TasteProfileModelFactory.create_async(user_id=other_user_db.id, name="my-profile")

        result = await import_taste_profile(user_id=user.id, taste_profile=taste_profile_db.to_entity(), uow=uow)

        assert result.user_id == user.id
        assert result.id != taste_profile_db.id

        stmt = select(TasteProfileModel).where(TasteProfileModel.name == "my-profile")
        rows = (await async_session_db.execute(stmt)).scalars().all()
        assert {row.user_id for row in rows} == {user.id, other_user_db.id}
