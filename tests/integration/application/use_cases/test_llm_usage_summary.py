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
        await LLMUsageModelFactory.create_async(user_id=user.id, operation=LLMOperation.DISCOVER, cost=Decimal(1))
        await LLMUsageModelFactory.create_async(user_id=other_db.id, cost=Decimal(2))

        summary = await summarize_llm_usage(user_id=user.id, group_by=LLMUsageGroupBy.OPERATION, since=None, uow=uow)

        assert [group.name for group in summary.groups] == ["discover"]
        assert summary.total.cost == Decimal(1)

    async def test__all_users(self, uow: UnitOfWorkPort, user: User) -> None:
        other_db = await UserModelFactory.create_async()
        await LLMUsageModelFactory.create_async(user_id=user.id, cost=Decimal(1))
        await LLMUsageModelFactory.create_async(user_id=other_db.id, cost=Decimal(2))

        summary = await summarize_llm_usage(user_id=None, group_by=LLMUsageGroupBy.USER, since=None, uow=uow)

        assert {group.name for group in summary.groups} == {user.email, other_db.email}
        assert summary.total.cost == Decimal(3)
