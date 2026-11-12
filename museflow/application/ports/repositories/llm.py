import uuid
from abc import ABC
from abc import abstractmethod
from datetime import date

from museflow.domain.entities.llm import LLMUsageRecord
from museflow.domain.enums import LLMOperation
from museflow.domain.enums import LLMUsageGroupBy
from museflow.domain.value_objects.llm import LLMUsageSummary


class LLMUsageRepository(ABC):
    """Port for the history of what the LLM calls cost."""

    @abstractmethod
    async def get_list(self, user_id: uuid.UUID) -> list[LLMUsageRecord]:
        """Every usage row of the user, oldest first."""
        ...

    @abstractmethod
    async def bulk_create(self, records: list[LLMUsageRecord]) -> None: ...

    @abstractmethod
    async def summarize(
        self,
        user_id: uuid.UUID | None,
        group_by: list[LLMUsageGroupBy],
        operation: LLMOperation | None = None,
        since: date | None = None,
        until: date | None = None,
    ) -> LLMUsageSummary:
        """Sums the LLM usage per group, with the grand total.

        The groups are sorted level by level, in the `group_by` order: months and runs chronologically, the other
        groupings by decreasing cost of the level (e.g. the priciest model first, then its efforts, priciest first).

        Args:
            user_id: The user whose usage is summed, or None for all the users.
            group_by: The groupings of the rows, one value per grouping in each group.
            operation: Only the runs of this operation, when given.
            since: Only the runs from this day on (UTC), when given.
            until: Only the runs up to this day included (UTC), when given.
        """
        ...
