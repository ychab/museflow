from decimal import Decimal

from museflow.domain.entities.user import User
from museflow.domain.enums import LLMOperation
from museflow.domain.enums import LLMUsageGroupBy
from museflow.infrastructure.entrypoints.cli.commands.llm.usage import usage_logic

from tests.integration.factories.models.llm import LLMUsageModelFactory


class TestUsageLogic:
    async def test__nominal(self, user: User) -> None:
        await LLMUsageModelFactory.create_async(user_id=user.id, operation=LLMOperation.DISCOVER, cost=Decimal(1))

        summary = await usage_logic(email=user.email, group_by=LLMUsageGroupBy.OPERATION, since=None)

        assert [group.name for group in summary.groups] == ["discover"]
        assert summary.total.cost == Decimal(1)
