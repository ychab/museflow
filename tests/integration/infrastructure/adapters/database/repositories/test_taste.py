import uuid

from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from museflow.application.ports.repositories.taste import TasteProfileRepository
from museflow.domain.entities.user import User
from museflow.domain.enums import TasteProfiler
from museflow.infrastructure.adapters.database.models.taste import TasteProfileModel

from tests.integration.factories.models.taste import TasteProfileDataFactory
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

    async def test__get_latest__found(self, user: User, taste_profile_repository: TasteProfileRepository) -> None:
        older_db = await TasteProfileModelFactory.create_async(user_id=user.id, profiler=TasteProfiler.GEMINI.value)
        newer_db = await TasteProfileModelFactory.create_async(user_id=user.id, profiler=TasteProfiler.GEMINI.value)

        result = await taste_profile_repository.get_latest(user_id=user.id, profiler=TasteProfiler.GEMINI)

        assert result is not None
        assert result.id == newer_db.id
        assert result.created_at == newer_db.created_at
        assert result.created_at >= older_db.created_at

    async def test__get_latest__not_found(self, taste_profile_repository: TasteProfileRepository) -> None:
        result = await taste_profile_repository.get_latest(user_id=uuid.uuid4(), profiler=TasteProfiler.GEMINI)
        assert result is None

    async def test__save_checkpoint__creates_and_updates(
        self,
        async_session_db: AsyncSession,
        user: User,
        taste_profile_repository: TasteProfileRepository,
    ) -> None:
        profile_data = TasteProfileDataFactory.build()

        await taste_profile_repository.save_checkpoint(
            user_id=user.id,
            name="my-profile",
            profiler=TasteProfiler.GEMINI,
            logic_version="v1.0",
            profiler_metadata={},
            tracks_count=100,
            profile_data=profile_data,
            batch_index=3,
        )

        stmt = select(TasteProfileModel).where(
            TasteProfileModel.user_id == user.id,
            TasteProfileModel.name == "my-profile",
        )
        row = (await async_session_db.execute(stmt)).scalar_one()
        assert row.checkpoint_batch_index == 3
        assert row.checkpoint_profile is not None

        # Second call updates the checkpoint
        await taste_profile_repository.save_checkpoint(
            user_id=user.id,
            name="my-profile",
            profiler=TasteProfiler.GEMINI,
            logic_version="v1.0",
            profiler_metadata={},
            tracks_count=100,
            profile_data=profile_data,
            batch_index=7,
        )

        await async_session_db.refresh(row)
        assert row.checkpoint_batch_index == 7

    async def test__get_checkpoint__found(
        self,
        user: User,
        taste_profile_repository: TasteProfileRepository,
    ) -> None:
        profile_data = TasteProfileDataFactory.build()

        await taste_profile_repository.save_checkpoint(
            user_id=user.id,
            name="my-profile",
            profiler=TasteProfiler.GEMINI,
            logic_version="v1.0",
            profiler_metadata={},
            tracks_count=50,
            profile_data=profile_data,
            batch_index=5,
        )

        result = await taste_profile_repository.get_checkpoint(user_id=user.id, name="my-profile")

        assert result is not None
        checkpoint_profile, checkpoint_index = result
        assert checkpoint_index == 5
        assert checkpoint_profile is not None

    async def test__get_checkpoint__not_found(
        self,
        taste_profile_repository: TasteProfileRepository,
    ) -> None:
        result = await taste_profile_repository.get_checkpoint(user_id=uuid.uuid4(), name="my-profile")
        assert result is None

    async def test__get_checkpoint__cleared_after_upsert(
        self,
        async_session_db: AsyncSession,
        user: User,
        taste_profile_repository: TasteProfileRepository,
    ) -> None:
        profile_data = TasteProfileDataFactory.build()

        await taste_profile_repository.save_checkpoint(
            user_id=user.id,
            name="my-profile",
            profiler=TasteProfiler.GEMINI,
            logic_version="v1.0",
            profiler_metadata={},
            tracks_count=100,
            profile_data=profile_data,
            batch_index=5,
        )

        final_profile = TasteProfileFactory.build(user_id=user.id, name="my-profile")
        await taste_profile_repository.upsert(final_profile)

        stmt = select(TasteProfileModel).where(
            TasteProfileModel.user_id == user.id,
            TasteProfileModel.name == "my-profile",
        )
        row = (await async_session_db.execute(stmt)).scalar_one()
        assert row.checkpoint_batch_index is None
        assert row.checkpoint_profile is None
