from museflow.application.ports.repositories.llm import LLMUsageRepository
from museflow.domain.entities.user import User
from museflow.infrastructure.entrypoints.cli.commands.llm.export import llm_export_logic
from museflow.infrastructure.entrypoints.cli.commands.llm.import_ import llm_import_logic

from tests.integration.factories.models.user import UserModelFactory
from tests.unit.factories.entities.llm import LLMUsageRecordFactory


class TestLlmImportLogic:
    async def test__nominal(self, user: User, llm_usage_repository: LLMUsageRepository) -> None:
        source_user_db = await UserModelFactory.create_async()
        records = LLMUsageRecordFactory.batch(2, user_id=source_user_db.id)
        await llm_usage_repository.bulk_create(records)
        # The data as the YAML file holds it: Decimal, timedelta and datetime as strings.
        data = [entry.model_dump(mode="json") for entry in await llm_export_logic(email=source_user_db.email)]

        result = await llm_import_logic(email=user.email, data=data)

        assert (result.imported_count, result.skipped_count) == (2, 0)
        imported = await llm_usage_repository.get_list(user_id=user.id)
        assert sorted((record.run_id, record.usage) for record in imported) == sorted(
            (record.run_id, record.usage) for record in records
        )
