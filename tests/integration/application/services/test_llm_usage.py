from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.application.services.llm_usage import record_llm_usage
from museflow.domain.entities.user import User
from museflow.domain.enums import LLMOperation
from museflow.infrastructure.adapters.database.models.llm import LLMUsageModel

from tests.integration.factories.models.playlist import PlaylistModelFactory
from tests.integration.factories.models.taste import TasteProfileModelFactory
from tests.unit.factories.value_objects.llm import LLMUsageFactory


class TestRecordLLMUsage:
    async def test__linked_to_the_profile_and_the_playlist(
        self,
        async_session_db: AsyncSession,
        user: User,
        uow: UnitOfWorkPort,
    ) -> None:
        profile_db = await TasteProfileModelFactory.create_async(user_id=user.id)
        playlist_db = await PlaylistModelFactory.create_async(user_id=user.id, profile_id=profile_db.id)
        usages = LLMUsageFactory.batch(2)

        await record_llm_usage(
            user_id=user.id,
            operation=LLMOperation.DISCOVER,
            usages=usages,
            uow=uow,
            profile_name=profile_db.name,
            playlist_id=playlist_db.id,
        )

        rows = list(
            (await async_session_db.execute(select(LLMUsageModel).where(LLMUsageModel.user_id == user.id))).scalars()
        )
        assert {row.to_entity().usage for row in rows} == set(usages)
        assert {(row.operation, row.profile_id, row.playlist_id) for row in rows} == {
            (LLMOperation.DISCOVER, profile_db.id, playlist_db.id)
        }
        assert len({row.run_id for row in rows}) == 1

    async def test__linked_to_nothing(
        self,
        async_session_db: AsyncSession,
        user: User,
        uow: UnitOfWorkPort,
    ) -> None:
        await record_llm_usage(
            user_id=user.id,
            operation=LLMOperation.ENRICH,
            usages=[LLMUsageFactory.build()],
            uow=uow,
        )

        row = (
            await async_session_db.execute(select(LLMUsageModel).where(LLMUsageModel.user_id == user.id))
        ).scalar_one()
        assert row.operation == LLMOperation.ENRICH
        assert row.profile_id is None
        assert row.playlist_id is None
