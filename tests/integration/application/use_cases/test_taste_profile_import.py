from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.application.use_cases.taste_profile_import import import_taste_profile
from museflow.domain.entities.user import User
from museflow.infrastructure.adapters.database.models.taste import TasteProfileModel

from tests.integration.factories.models.taste import TasteProfileModelFactory


class TestImportTasteProfileUseCase:
    async def test__nominal(self, user: User, uow: UnitOfWorkPort, async_session_db: AsyncSession) -> None:
        taste_profile_db = await TasteProfileModelFactory.create_async(user_id=user.id, name="my-profile")

        result = await import_taste_profile(user_id=user.id, taste_profile=taste_profile_db.to_entity(), uow=uow)

        assert result.name == "my-profile"
        assert result.user_id == user.id

        stmt = select(TasteProfileModel).where(TasteProfileModel.user_id == user.id)
        rows = (await async_session_db.execute(stmt)).scalars().all()
        assert len(rows) == 1
