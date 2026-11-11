from datetime import UTC
from datetime import datetime

from museflow.application.ports.repositories.llm import LLMUsageRepository
from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.application.use_cases.llm_usage_export import export_llm_usage
from museflow.domain.entities.user import User

from tests.integration.factories.models.taste import TasteProfileModelFactory
from tests.unit.factories.entities.llm import LLMUsageRecordFactory


class TestExportLLMUsageUseCase:
    async def test__nominal(self, user: User, uow: UnitOfWorkPort, llm_usage_repository: LLMUsageRepository) -> None:
        profile_db = await TasteProfileModelFactory.create_async(user_id=user.id, name="my-profile")
        with_profile = LLMUsageRecordFactory.build(
            user_id=user.id,
            profile_id=profile_db.id,
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        without_profile = LLMUsageRecordFactory.build(user_id=user.id, created_at=datetime(2026, 2, 1, tzinfo=UTC))
        await llm_usage_repository.bulk_create([without_profile, with_profile])

        entries = await export_llm_usage(user_id=user.id, uow=uow)

        assert [entry.profile_name for entry in entries] == ["my-profile", None]
        entry = entries[0]
        assert (entry.run_id, entry.operation, entry.created_at) == (
            with_profile.run_id,
            with_profile.operation,
            with_profile.created_at,
        )
        assert (entry.step, entry.model, entry.reasoning_effort, entry.calls, entry.cost, entry.duration) == (
            with_profile.usage.step,
            with_profile.usage.model,
            with_profile.usage.reasoning_effort,
            with_profile.usage.calls,
            with_profile.usage.cost,
            with_profile.usage.duration,
        )
