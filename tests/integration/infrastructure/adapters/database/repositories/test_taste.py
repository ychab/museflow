import uuid

from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from museflow.application.ports.repositories.taste import TasteProfileRepository
from museflow.domain.entities.user import User
from museflow.domain.types import TasteProfiler
from museflow.infrastructure.adapters.database.models.taste import TasteProfileModel

from tests.integration.factories.models.taste import TasteProfileModelFactory
from tests.unit.factories.entities.taste import TasteProfileFactory


class TestTasteProfileSQLRepository:
    async def test__upsert__create(
        self,
        async_session_db: AsyncSession,
        user: User,
        taste_profile_repository: TasteProfileRepository,
    ) -> None:
        profile = TasteProfileFactory.build(
            user_id=user.id,
            profiler=TasteProfiler.GEMINI,
            name="my-profile",
            tracks_count=100,
            logic_version="1.0",
        )

        result = await taste_profile_repository.upsert(profile)

        assert result.id == profile.id
        assert result.user_id == user.id
        assert result.profiler == TasteProfiler.GEMINI
        assert result.tracks_count == 100
        assert result.logic_version == "1.0"

        stmt = select(func.count()).select_from(TasteProfileModel).where(TasteProfileModel.id == profile.id)
        count = (await async_session_db.execute(stmt)).scalar()
        assert count == 1

    async def test__upsert__update(self, user: User, taste_profile_repository: TasteProfileRepository) -> None:
        profile_v1 = TasteProfileFactory.build(
            user_id=user.id,
            profiler=TasteProfiler.GEMINI,
            name="my-profile",
            tracks_count=10,
            logic_version="1.0",
        )
        profile_v1 = await taste_profile_repository.upsert(profile_v1)

        profile_v2 = TasteProfileFactory.build(
            user_id=user.id,
            profiler=TasteProfiler.GEMINI,
            name="my-profile",
            tracks_count=99,
            logic_version="2.0",
        )
        assert profile_v2.id != profile_v1.id  # In the beginning, the ids are different

        profile_v2 = await taste_profile_repository.upsert(profile_v2)

        assert profile_v2.id == profile_v1.id  # then once merge, the original id is preserved
        assert profile_v2.tracks_count == 99
        assert profile_v2.logic_version == "2.0"

    async def test__get__found(self, user: User, taste_profile_repository: TasteProfileRepository) -> None:
        profile_db = await TasteProfileModelFactory.create_async(user_id=user.id, name="my-profile")
        await TasteProfileModelFactory.create_async()  # Another user

        profile_get = await taste_profile_repository.get(user_id=user.id, name="my-profile")

        assert profile_get is not None
        assert profile_get.id == profile_db.id

    async def test__get__not_found(self, taste_profile_repository: TasteProfileRepository) -> None:
        result = await taste_profile_repository.get(user_id=uuid.uuid4(), name="my-profile")
        assert result is None
