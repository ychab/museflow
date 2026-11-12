import uuid
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from decimal import Decimal

import pytest

from museflow.application.inputs.llm import LLMUsageEntryInput
from museflow.application.ports.repositories.llm import LLMUsageRepository
from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.application.use_cases.llm_usage_export import export_llm_usage
from museflow.application.use_cases.llm_usage_import import import_llm_usage
from museflow.domain.entities.user import User
from museflow.domain.enums import LLMOperation
from museflow.domain.enums import ReasoningEffort

from tests.integration.factories.models.taste import TasteProfileModelFactory
from tests.integration.factories.models.user import UserModelFactory
from tests.unit.factories.entities.llm import LLMUsageRecordFactory
from tests.unit.factories.value_objects.llm import LLMUsageFactory


class TestImportLLMUsageUseCase:
    @pytest.fixture
    def entry(self) -> LLMUsageEntryInput:
        return LLMUsageEntryInput(
            run_id=uuid.uuid4(),
            operation=LLMOperation.TASTE_BUILD,
            profile_name="my-profile",
            step="profiler_merge",
            model="google/gemini-3.5-flash",
            reasoning_effort=ReasoningEffort.LOW,
            calls=3,
            prompt_tokens=1200,
            completion_tokens=900,
            reasoning_tokens=400,
            cost=Decimal("0.012345"),
            duration=timedelta(seconds=42),
            created_at=datetime(2026, 1, 15, 10, 30, tzinfo=UTC),
        )

    async def test__round_trip(
        self,
        user: User,
        uow: UnitOfWorkPort,
        llm_usage_repository: LLMUsageRepository,
    ) -> None:
        source_user_db = await UserModelFactory.create_async()
        source_profile_db = await TasteProfileModelFactory.create_async(user_id=source_user_db.id, name="my-profile")
        profile_db = await TasteProfileModelFactory.create_async(user_id=user.id, name="my-profile")
        records = [
            LLMUsageRecordFactory.build(
                user_id=source_user_db.id,
                profile_id=source_profile_db.id,
                usage=LLMUsageFactory.build(reasoning_effort=ReasoningEffort.LOW),
            ),
            LLMUsageRecordFactory.build(
                user_id=source_user_db.id,
                usage=LLMUsageFactory.build(reasoning_effort=ReasoningEffort.HIGH),
            ),
        ]
        await llm_usage_repository.bulk_create(records)
        entries = await export_llm_usage(user_id=source_user_db.id, uow=uow)

        result = await import_llm_usage(user_id=user.id, entries=entries, uow=uow)

        assert (result.imported_count, result.skipped_count) == (2, 0)
        imported = await llm_usage_repository.get_list(user_id=user.id)
        assert [(record.run_id, record.usage, record.created_at) for record in imported] == [
            (record.run_id, record.usage, record.created_at) for record in sorted(records, key=lambda r: r.created_at)
        ]
        # The profile link follows the name to the importing user's profile.
        assert {record.profile_id for record in imported} == {profile_db.id, None}

    async def test__already_there__skipped(
        self,
        user: User,
        uow: UnitOfWorkPort,
        llm_usage_repository: LLMUsageRepository,
        entry: LLMUsageEntryInput,
    ) -> None:
        await import_llm_usage(user_id=user.id, entries=[entry], uow=uow)

        result = await import_llm_usage(user_id=user.id, entries=[entry, entry], uow=uow)

        assert (result.imported_count, result.skipped_count) == (0, 2)
        assert len(await llm_usage_repository.get_list(user_id=user.id)) == 1

    async def test__profile_unknown__unlinked(
        self,
        user: User,
        uow: UnitOfWorkPort,
        llm_usage_repository: LLMUsageRepository,
        entry: LLMUsageEntryInput,
    ) -> None:
        result = await import_llm_usage(user_id=user.id, entries=[entry], uow=uow)

        assert result.imported_count == 1
        [record] = await llm_usage_repository.get_list(user_id=user.id)
        assert record.profile_id is None
