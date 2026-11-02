from sqlalchemy.ext.asyncio import AsyncSession

from museflow.application.ports.repositories.llm import LLMUsageRepository
from museflow.domain.entities.llm import LLMUsageRecord
from museflow.infrastructure.adapters.database.models.llm import LLMUsageModel


class LLMUsageSQLRepository(LLMUsageRepository):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add_many(self, records: list[LLMUsageRecord]) -> None:
        self.session.add_all([LLMUsageModel.from_entity(record) for record in records])
        await self.session.flush()
