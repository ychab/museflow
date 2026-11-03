from decimal import Decimal

from museflow.domain.entities.user import User
from museflow.domain.enums import LLMOperation
from museflow.domain.enums import LLMUsageGroupBy
from museflow.infrastructure.entrypoints.cli.commands.llm.usage import usage_logic

from tests.integration.factories.models.llm import LLMUsageModelFactory
from tests.integration.factories.models.user import UserModelFactory


class TestUsageLogic:
    async def test__nominal(self, user: User) -> None:
        await LLMUsageModelFactory.create_async(user_id=user.id, operation=LLMOperation.DISCOVER, cost=Decimal(1))

        summary = await usage_logic(email=user.email, group_by=LLMUsageGroupBy.OPERATION, since=None)

        assert [group.name for group in summary.groups] == ["discover"]
        assert summary.total.cost == Decimal(1)

    async def test__all_users(self, user: User) -> None:
        other_db = await UserModelFactory.create_async()
        await LLMUsageModelFactory.create_async(user_id=user.id, cost=Decimal(1))
        await LLMUsageModelFactory.create_async(user_id=other_db.id, cost=Decimal(2))

        summary = await usage_logic(email=None, group_by=LLMUsageGroupBy.USER, since=None)

        assert {group.name for group in summary.groups} == {user.email, other_db.email}
        assert summary.total.cost == Decimal(3)
