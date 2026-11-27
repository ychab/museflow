import uuid
from datetime import timedelta

from sqlalchemy import delete
from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from museflow.application.ports.repositories.taste_build import TasteProfileBuildRepository
from museflow.infrastructure.adapters.database.models import TasteProfileBuildModel


class TasteProfileBuildSQLRepository(TasteProfileBuildRepository):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def claim(self, user_id: uuid.UUID, name: str, build_id: uuid.UUID, lease_duration: timedelta) -> bool:
        insert_stmt = pg_insert(TasteProfileBuildModel).values(
            id=uuid.uuid4(),
            user_id=user_id,
            name=name,
            build_id=build_id,
            lease_until=func.now() + lease_duration,
        )
        # A held lease is left as it is: no row is updated, so none returned. Two claims at once queue on the row
        # lock, and the second sees the lease the first just took.
        stmt = insert_stmt.on_conflict_do_update(
            constraint="uq_museflow_taste_profile_build_user_name",
            set_={"build_id": insert_stmt.excluded.build_id, "lease_until": insert_stmt.excluded.lease_until},
            where=TasteProfileBuildModel.lease_until < func.now(),
        ).returning(TasteProfileBuildModel.id)

        result = await self.session.execute(stmt)
        claimed = result.scalar_one_or_none() is not None
        return claimed

    async def renew(self, user_id: uuid.UUID, name: str, build_id: uuid.UUID, lease_duration: timedelta) -> bool:
        stmt = (
            update(TasteProfileBuildModel)
            .where(
                TasteProfileBuildModel.user_id == user_id,
                TasteProfileBuildModel.name == name,
                TasteProfileBuildModel.build_id == build_id,
            )
            .values(lease_until=func.now() + lease_duration)
            .returning(TasteProfileBuildModel.id)
        )
        result = await self.session.execute(stmt)
        renewed = result.scalar_one_or_none() is not None
        return renewed

    async def is_held(self, user_id: uuid.UUID, name: str) -> bool:
        stmt = select(
            select(TasteProfileBuildModel)
            .where(
                TasteProfileBuildModel.user_id == user_id,
                TasteProfileBuildModel.name == name,
                TasteProfileBuildModel.lease_until >= func.now(),
            )
            .exists()
        )
        return (await self.session.execute(stmt)).scalar_one()

    async def release(self, user_id: uuid.UUID, name: str, build_id: uuid.UUID) -> None:
        stmt = delete(TasteProfileBuildModel).where(
            TasteProfileBuildModel.user_id == user_id,
            TasteProfileBuildModel.name == name,
            TasteProfileBuildModel.build_id == build_id,
        )
        await self.session.execute(stmt)
