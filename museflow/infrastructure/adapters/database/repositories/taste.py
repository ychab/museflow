import uuid

from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from museflow.application.ports.repositories.taste import TasteProfileRepository
from museflow.domain.entities.taste import TasteProfile
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
