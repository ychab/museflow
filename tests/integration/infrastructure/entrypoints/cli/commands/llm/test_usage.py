from datetime import UTC
from datetime import date
from datetime import datetime
from decimal import Decimal

from museflow.domain.entities.user import User
from museflow.domain.enums import LLMOperation
from museflow.domain.enums import LLMUsageGroupBy
from museflow.infrastructure.entrypoints.cli.commands.llm.usage import llm_usage_logic

from tests.integration.factories.models.llm import LLMUsageModelFactory
from tests.integration.factories.models.user import UserModelFactory


class TestLLMUsageLogic:
    async def test__nominal(self, user: User) -> None:
        await LLMUsageModelFactory.create_async(
            user_id=user.id,
            operation=LLMOperation.DISCOVER,
            model="openai/gpt-5-mini",
            created_at=datetime(2026, 11, 2, tzinfo=UTC),
            cost=Decimal(1),
        )
        # Filtered out by the operation, then by the period.
        await LLMUsageModelFactory.create_async(user_id=user.id, operation=LLMOperation.ENRICH, cost=Decimal(4))
        await LLMUsageModelFactory.create_async(
            user_id=user.id, operation=LLMOperation.DISCOVER, created_at=datetime(2026, 11, 4, tzinfo=UTC)
        )

        summary = await llm_usage_logic(
            email=user.email,
            group_by=[LLMUsageGroupBy.OPERATION, LLMUsageGroupBy.MODEL],
            operation=LLMOperation.DISCOVER,
            since=date(2026, 11, 1),
            until=date(2026, 11, 3),
        )

        assert [group.values for group in summary.groups] == [["discover", "openai/gpt-5-mini"]]
        assert summary.total.cost == Decimal(1)

    async def test__all_users(self, user: User) -> None:
        other_db = await UserModelFactory.create_async()
        await LLMUsageModelFactory.create_async(user_id=user.id, cost=Decimal(1))
        await LLMUsageModelFactory.create_async(user_id=other_db.id, cost=Decimal(2))

        summary = await llm_usage_logic(
            email=None, group_by=[LLMUsageGroupBy.USER], operation=None, since=None, until=None
        )

        assert {group.values[0] for group in summary.groups} == {user.email, other_db.email}
        assert summary.total.cost == Decimal(3)
