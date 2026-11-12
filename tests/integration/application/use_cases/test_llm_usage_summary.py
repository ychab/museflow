from datetime import UTC
from datetime import date
from datetime import datetime
from decimal import Decimal

from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.application.use_cases.llm_usage_summary import summarize_llm_usage
from museflow.domain.entities.user import User
from museflow.domain.enums import LLMOperation
from museflow.domain.enums import LLMUsageGroupBy

from tests.integration.factories.models.llm import LLMUsageModelFactory
from tests.integration.factories.models.user import UserModelFactory


class TestSummarizeLLMUsageUseCase:
    async def test__nominal(self, uow: UnitOfWorkPort, user: User) -> None:
        other_db = await UserModelFactory.create_async()
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
        await LLMUsageModelFactory.create_async(user_id=other_db.id, cost=Decimal(2))

        summary = await summarize_llm_usage(
            user_id=user.id,
            group_by=[LLMUsageGroupBy.OPERATION, LLMUsageGroupBy.MODEL],
            operation=LLMOperation.DISCOVER,
            since=date(2026, 11, 1),
            until=date(2026, 11, 3),
            uow=uow,
        )

        assert [group.values for group in summary.groups] == [["discover", "openai/gpt-5-mini"]]
        assert summary.total.cost == Decimal(1)

    async def test__all_users(self, uow: UnitOfWorkPort, user: User) -> None:
        other_db = await UserModelFactory.create_async()
        await LLMUsageModelFactory.create_async(user_id=user.id, cost=Decimal(1))
        await LLMUsageModelFactory.create_async(user_id=other_db.id, cost=Decimal(2))

        summary = await summarize_llm_usage(
            user_id=None, group_by=[LLMUsageGroupBy.USER], operation=None, since=None, until=None, uow=uow
        )

        assert {group.values[0] for group in summary.groups} == {user.email, other_db.email}
        assert summary.total.cost == Decimal(3)
