import dataclasses
from unittest import mock

from sqlalchemy import delete
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from museflow.application.ports.repositories.llm import LLMUsageRepository
from museflow.domain.entities.user import User
from museflow.infrastructure.adapters.database.models.llm import LLMUsageModel
from museflow.infrastructure.adapters.database.models.playlist import Playlist as PlaylistModel
from museflow.infrastructure.adapters.database.models.taste import TasteProfileModel

from tests.integration.factories.models.playlist import PlaylistModelFactory
from tests.integration.factories.models.taste import TasteProfileModelFactory
from tests.unit.factories.entities.llm import LLMUsageRecordFactory


class TestLLMUsageSQLRepository:
    async def test__add_many__nominal(
        self,
        async_session_db: AsyncSession,
        user: User,
        llm_usage_repository: LLMUsageRepository,
    ) -> None:
        records = LLMUsageRecordFactory.batch(2, user_id=user.id)

        await llm_usage_repository.add_many(records)

        rows = (
            await async_session_db.execute(select(LLMUsageModel).where(LLMUsageModel.user_id == user.id))
        ).scalars()
        saved = sorted((row.to_entity() for row in rows), key=lambda record: record.id)
        expected = sorted(
            (dataclasses.replace(record, created_at=mock.ANY) for record in records), key=lambda record: record.id
        )
        assert saved == expected

    async def test__profile_deleted__history_kept(
        self,
        async_session_db: AsyncSession,
        user: User,
        llm_usage_repository: LLMUsageRepository,
    ) -> None:
        profile_db = await TasteProfileModelFactory.create_async(user_id=user.id)
        record = LLMUsageRecordFactory.build(user_id=user.id, profile_id=profile_db.id)
        await llm_usage_repository.add_many([record])

        await async_session_db.execute(delete(TasteProfileModel).where(TasteProfileModel.id == profile_db.id))

        profile_id = (
            await async_session_db.execute(select(LLMUsageModel.profile_id).where(LLMUsageModel.id == record.id))
        ).scalar_one()
        assert profile_id is None

    async def test__playlist_deleted__history_kept(
        self,
        async_session_db: AsyncSession,
        user: User,
        llm_usage_repository: LLMUsageRepository,
    ) -> None:
        playlist_db = await PlaylistModelFactory.create_async(user_id=user.id)
        record = LLMUsageRecordFactory.build(user_id=user.id, playlist_id=playlist_db.id)
        await llm_usage_repository.add_many([record])

        await async_session_db.execute(delete(PlaylistModel).where(PlaylistModel.id == playlist_db.id))

        playlist_id = (
            await async_session_db.execute(select(LLMUsageModel.playlist_id).where(LLMUsageModel.id == record.id))
        ).scalar_one()
        assert playlist_id is None
