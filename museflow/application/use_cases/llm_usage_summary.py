import uuid
from datetime import date

from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.domain.enums import LLMOperation
from museflow.domain.enums import LLMUsageGroupBy
from museflow.domain.value_objects.llm import LLMUsageSummary


async def summarize_llm_usage(
    user_id: uuid.UUID | None,
    group_by: list[LLMUsageGroupBy],
    operation: LLMOperation | None,
    since: date | None,
    until: date | None,
    uow: UnitOfWorkPort,
) -> LLMUsageSummary:
    async with uow:
        return await uow.llm_usage.summarize(
            user_id=user_id,
            group_by=group_by,
            operation=operation,
            since=since,
            until=until,
        )
