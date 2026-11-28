import logging
import uuid
from unittest import mock

import pytest

from museflow.application.services.llm_usage import LLMUsageService
from museflow.domain.entities.user import User
from museflow.domain.enums import LLMOperation

from tests.unit.factories.value_objects.llm import LLMUsageFactory


class TestLLMUsageServiceSave:
    async def test__no_usage__nothing_recorded(
        self,
        user: User,
        mock_uow: mock.AsyncMock,
        mock_llm_usage_repository: mock.AsyncMock,
    ) -> None:
        await LLMUsageService(uow=mock_uow).save(
            user_id=user.id, run_id=uuid.uuid4(), operation=LLMOperation.ENRICH, usages=[]
        )

        mock_uow.__aenter__.assert_not_awaited()
        mock_llm_usage_repository.bulk_accumulate.assert_not_awaited()

    async def test__profile_not_found__recorded_without_profile(
        self,
        user: User,
        mock_uow: mock.AsyncMock,
        mock_taste_profile_repository: mock.AsyncMock,
        mock_llm_usage_repository: mock.AsyncMock,
    ) -> None:
        # A build paused before its first checkpoint left no profile behind.
        mock_taste_profile_repository.get.return_value = None

        await LLMUsageService(uow=mock_uow).save(
            user_id=user.id,
            run_id=uuid.uuid4(),
            operation=LLMOperation.TASTE_BUILD,
            usages=[LLMUsageFactory.build()],
            profile_name="my-profile",
        )

        (record,) = mock_llm_usage_repository.bulk_accumulate.call_args.args[0]
        assert record.profile_id is None

    async def test__failure__logged_not_raised(
        self,
        user: User,
        mock_uow: mock.AsyncMock,
        mock_llm_usage_repository: mock.AsyncMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        mock_llm_usage_repository.bulk_accumulate.side_effect = RuntimeError("database down")

        with caplog.at_level(logging.ERROR):
            await LLMUsageService(uow=mock_uow).save(
                user_id=user.id,
                run_id=uuid.uuid4(),
                operation=LLMOperation.ENRICH,
                usages=[LLMUsageFactory.build()],
            )

        (record,) = caplog.records
        assert record.getMessage() == "Failed to save the LLM usage"
        assert record.__dict__["user_id"] == str(user.id)
        assert record.__dict__["operation"] == "enrich"
        assert record.exc_info is not None
