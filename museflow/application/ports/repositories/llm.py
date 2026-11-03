import uuid
from abc import ABC
from abc import abstractmethod
from datetime import date

from museflow.domain.entities.llm import LLMUsageRecord
from museflow.domain.enums import LLMUsageGroupBy
from museflow.domain.value_objects.llm import LLMUsageSummary


class LLMUsageRepository(ABC):
    """Port for the history of what the LLM calls cost."""

    @abstractmethod
    async def add_many(self, records: list[LLMUsageRecord]) -> None: ...

    @abstractmethod
    async def summarize(
        self,
        user_id: uuid.UUID,
        group_by: LLMUsageGroupBy,
        since: date | None = None,
    ) -> LLMUsageSummary:
        """Sums the user's LLM usage per group, months in chronological order, other groups by decreasing cost.

        Args:
            user_id: The user whose usage is summed.
            group_by: The grouping of the rows.
            since: Only the runs from this day on (UTC), when given.
        """
        ...
