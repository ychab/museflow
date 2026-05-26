import uuid
from typing import Any

from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from museflow.application.ports.repositories.taste import TasteProfileRepository
from museflow.domain.entities.taste import TasteProfile
from museflow.domain.entities.taste import TasteProfileData
from museflow.domain.entities.taste import TasteProfileStatus
from museflow.domain.types import TasteProfiler
from museflow.infrastructure.adapters.database.models.taste import TasteProfileModel


class TasteProfileSQLRepository(TasteProfileRepository):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert(self, profile: TasteProfile) -> TasteProfile:
        stmt = pg_insert(TasteProfileModel).values(
            id=profile.id,
            name=profile.name,
            user_id=profile.user_id,
            profiler=profile.profiler,
            profile=profile.profile,
            profiler_metadata=profile.profiler_metadata,
            tracks_count=profile.tracks_count,
            logic_version=profile.logic_version,
        )

        upsert_stmt = stmt.on_conflict_do_update(
            constraint="uq_museflow_taste_profile_user_name",
            set_={
                "profile": stmt.excluded.profile,
                "profiler_metadata": stmt.excluded.profiler_metadata,
                "tracks_count": stmt.excluded.tracks_count,
                "logic_version": stmt.excluded.logic_version,
                "status": TasteProfileStatus.FINISHED,
                "checkpoint_profile": None,
                "checkpoint_batch_index": None,
                "updated_at": func.now(),
            },
        ).returning(TasteProfileModel)

        profile_db = (await self.session.execute(upsert_stmt)).scalar_one()
        await self.session.commit()

        return profile_db.to_entity()

    async def get(self, user_id: uuid.UUID, name: str) -> TasteProfile | None:
        stmt = select(TasteProfileModel).where(
            TasteProfileModel.user_id == user_id,
            TasteProfileModel.name == name,
        )
        profile_db = (await self.session.execute(stmt)).scalar_one_or_none()
        return profile_db.to_entity() if profile_db else None

    async def get_latest(self, user_id: uuid.UUID, profiler: TasteProfiler) -> TasteProfile | None:
        stmt = (
            select(TasteProfileModel)
            .where(TasteProfileModel.user_id == user_id)
            .where(TasteProfileModel.profiler == profiler.value)
            .order_by(TasteProfileModel.created_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        profile_db = result.scalar_one_or_none()
        return profile_db.to_entity() if profile_db else None

    async def save_checkpoint(
        self,
        user_id: uuid.UUID,
        name: str,
        profiler: TasteProfiler,
        logic_version: str,
        profiler_metadata: dict[str, Any],
        tracks_count: int,
        profile_data: TasteProfileData,
        batch_index: int,
    ) -> None:
        insert_stmt = pg_insert(TasteProfileModel).values(
            id=uuid.uuid4(),
            name=name,
            user_id=user_id,
            profiler=profiler,
            profile=profile_data,
            profiler_metadata=profiler_metadata,
            tracks_count=tracks_count,
            logic_version=logic_version,
            checkpoint_profile=profile_data,
            checkpoint_batch_index=batch_index,
        )
        upsert_stmt = insert_stmt.on_conflict_do_update(
            constraint="uq_museflow_taste_profile_user_name",
            set_={
                "profile": insert_stmt.excluded.profile,
                "profiler_metadata": insert_stmt.excluded.profiler_metadata,
                "tracks_count": insert_stmt.excluded.tracks_count,
                "logic_version": insert_stmt.excluded.logic_version,
                "status": TasteProfileStatus.BUILDING,
                "checkpoint_profile": insert_stmt.excluded.checkpoint_profile,
                "checkpoint_batch_index": insert_stmt.excluded.checkpoint_batch_index,
                "updated_at": func.now(),
            },
        )
        await self.session.execute(upsert_stmt)
        await self.session.commit()

    async def get_checkpoint(self, user_id: uuid.UUID, name: str) -> tuple[TasteProfileData, int] | None:
        stmt = select(TasteProfileModel).where(
            TasteProfileModel.user_id == user_id,
            TasteProfileModel.name == name,
            TasteProfileModel.checkpoint_batch_index.isnot(None),
        )
        profile_db = (await self.session.execute(stmt)).scalar_one_or_none()
        if profile_db is None or profile_db.checkpoint_profile is None or profile_db.checkpoint_batch_index is None:
            return None
        return profile_db.checkpoint_profile, profile_db.checkpoint_batch_index
