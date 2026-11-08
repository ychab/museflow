from museflow.application.ports.repositories.llm import LLMUsageRepository
from museflow.domain.entities.user import User
from museflow.infrastructure.entrypoints.cli.commands.llm.export import llm_export_logic

from tests.unit.factories.entities.llm import LLMUsageRecordFactory


class TestLlmExportLogic:
    async def test__nominal(self, user: User, llm_usage_repository: LLMUsageRepository) -> None:
        record = LLMUsageRecordFactory.build(user_id=user.id)
        await llm_usage_repository.bulk_create([record])

        entries = await llm_export_logic(email=user.email)

        assert [(entry.run_id, entry.step, entry.cost) for entry in entries] == [
            (record.run_id, record.usage.step, record.usage.cost)
        ]
