from abc import ABC
from abc import abstractmethod

from museflow.domain.entities.llm import LLMUsageRecord


class LLMUsageRepository(ABC):
    """Port for the history of what the LLM calls cost."""

    @abstractmethod
    async def add_many(self, records: list[LLMUsageRecord]) -> None: ...
