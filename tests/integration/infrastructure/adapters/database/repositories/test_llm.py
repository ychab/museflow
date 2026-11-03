import dataclasses
import uuid
from datetime import UTC
from datetime import date
from datetime import datetime
from decimal import Decimal
from unittest import mock

from sqlalchemy import delete
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from museflow.application.ports.repositories.llm import LLMUsageRepository
from museflow.domain.entities.user import User
from museflow.domain.enums import LLMOperation
from museflow.domain.enums import LLMUsageGroupBy
from museflow.domain.value_objects.llm import LLMUsageGroup
from museflow.domain.value_objects.llm import LLMUsageSummary
from museflow.domain.value_objects.llm import LLMUsageTotals
from museflow.infrastructure.adapters.database.models.llm import LLMUsageModel
from museflow.infrastructure.adapters.database.models.playlist import Playlist as PlaylistModel
from museflow.infrastructure.adapters.database.models.taste import TasteProfileModel

from tests.integration.factories.models.llm import LLMUsageModelFactory
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

    async def test__summarize__empty(self, user: User, llm_usage_repository: LLMUsageRepository) -> None:
        summary = await llm_usage_repository.summarize(user_id=user.id, group_by=LLMUsageGroupBy.OPERATION)
        assert summary == LLMUsageSummary(groups=[], total=LLMUsageTotals())

    async def test__summarize__by_operation(self, user: User, llm_usage_repository: LLMUsageRepository) -> None:
        await LLMUsageModelFactory.create_async(
            user_id=user.id,
            operation=LLMOperation.ENRICH,
            calls=1,
            prompt_tokens=100,
            completion_tokens=50,
            reasoning_tokens=10,
            cost=Decimal("0.010000"),
        )
        for cost in ("0.020000", "0.030000"):
            await LLMUsageModelFactory.create_async(
                user_id=user.id,
                operation=LLMOperation.DISCOVER,
                calls=3,
                prompt_tokens=1000,
                completion_tokens=500,
                reasoning_tokens=200,
                cost=Decimal(cost),
            )
        # Another user's spending stays out.
        await LLMUsageModelFactory.create_async(operation=LLMOperation.DISCOVER)

        summary = await llm_usage_repository.summarize(user_id=user.id, group_by=LLMUsageGroupBy.OPERATION)

        assert summary == LLMUsageSummary(
            groups=[
                LLMUsageGroup(
                    name="discover",
                    totals=LLMUsageTotals(
                        runs=2,
                        calls=6,
                        prompt_tokens=2000,
                        completion_tokens=1000,
                        reasoning_tokens=400,
                        cost=Decimal("0.050000"),
                    ),
                ),
                LLMUsageGroup(
                    name="enrich",
                    totals=LLMUsageTotals(
                        runs=1,
                        calls=1,
                        prompt_tokens=100,
                        completion_tokens=50,
                        reasoning_tokens=10,
                        cost=Decimal("0.010000"),
                    ),
                ),
            ],
            total=LLMUsageTotals(
                runs=3,
                calls=7,
                prompt_tokens=2100,
                completion_tokens=1050,
                reasoning_tokens=410,
                cost=Decimal("0.060000"),
            ),
        )

    async def test__summarize__by_step__run_counted_once_in_total(
        self,
        user: User,
        llm_usage_repository: LLMUsageRepository,
    ) -> None:
        run_id = uuid.uuid4()
        await LLMUsageModelFactory.create_async(
            user_id=user.id, run_id=run_id, step="profiler segment", cost=Decimal("0.300000")
        )
        await LLMUsageModelFactory.create_async(
            user_id=user.id, run_id=run_id, step="profiler merge", cost=Decimal("0.100000")
        )

        summary = await llm_usage_repository.summarize(user_id=user.id, group_by=LLMUsageGroupBy.STEP)

        assert [(group.name, group.totals.runs, group.totals.cost) for group in summary.groups] == [
            ("profiler segment", 1, Decimal("0.300000")),
            ("profiler merge", 1, Decimal("0.100000")),
        ]
        assert summary.total.runs == 1
        assert summary.total.cost == Decimal("0.400000")

    async def test__summarize__by_model(self, user: User, llm_usage_repository: LLMUsageRepository) -> None:
        await LLMUsageModelFactory.create_async(user_id=user.id, model="google/gemini-3.5-flash", cost=Decimal(1))
        await LLMUsageModelFactory.create_async(user_id=user.id, model="openai/gpt-5-mini", cost=Decimal(2))

        summary = await llm_usage_repository.summarize(user_id=user.id, group_by=LLMUsageGroupBy.MODEL)

        assert [group.name for group in summary.groups] == ["openai/gpt-5-mini", "google/gemini-3.5-flash"]

    async def test__summarize__by_month__chronological(
        self,
        user: User,
        llm_usage_repository: LLMUsageRepository,
    ) -> None:
        for month, cost in ((10, 1), (9, 3), (11, 2)):
            await LLMUsageModelFactory.create_async(
                user_id=user.id, created_at=datetime(2026, month, 15, tzinfo=UTC), cost=Decimal(cost)
            )

        summary = await llm_usage_repository.summarize(user_id=user.id, group_by=LLMUsageGroupBy.MONTH)

        assert [group.name for group in summary.groups] == ["2026-09", "2026-10", "2026-11"]

    async def test__summarize__by_profile(self, user: User, llm_usage_repository: LLMUsageRepository) -> None:
        profile_db = await TasteProfileModelFactory.create_async(user_id=user.id, name="evening")
        await LLMUsageModelFactory.create_async(user_id=user.id, profile_id=profile_db.id, cost=Decimal(2))
        await LLMUsageModelFactory.create_async(user_id=user.id, profile_id=None, cost=Decimal(1))

        summary = await llm_usage_repository.summarize(user_id=user.id, group_by=LLMUsageGroupBy.PROFILE)

        assert [group.name for group in summary.groups] == ["evening", None]

    async def test__summarize__since(self, user: User, llm_usage_repository: LLMUsageRepository) -> None:
        await LLMUsageModelFactory.create_async(
            user_id=user.id, created_at=datetime(2026, 10, 31, 23, 59, tzinfo=UTC), cost=Decimal(1)
        )
        await LLMUsageModelFactory.create_async(
            user_id=user.id, created_at=datetime(2026, 11, 1, 0, 0, tzinfo=UTC), cost=Decimal(2)
        )

        summary = await llm_usage_repository.summarize(
            user_id=user.id, group_by=LLMUsageGroupBy.MONTH, since=date(2026, 11, 1)
        )

        assert [group.name for group in summary.groups] == ["2026-11"]
        assert summary.total.cost == Decimal(2)
