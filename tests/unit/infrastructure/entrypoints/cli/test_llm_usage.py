import logging
from decimal import Decimal
from unittest import mock

import pytest

from museflow.domain.entities.user import User
from museflow.domain.enums import LLMOperation
from museflow.infrastructure.adapters.common.llm.schemas import ChatUsage
from museflow.infrastructure.adapters.common.llm.usage import LLMUsageMeter
from museflow.infrastructure.entrypoints.cli.llm_usage import print_llm_usage
from museflow.infrastructure.entrypoints.cli.llm_usage import save_llm_usage

from tests.unit.infrastructure.entrypoints.cli.conftest import spend


class TestPrintLLMUsage:
    def test__no_call__prints_nothing(self, capsys: pytest.CaptureFixture[str]) -> None:
        print_llm_usage(LLMUsageMeter())

        assert capsys.readouterr().out == ""

    def test__prints_each_step_and_the_total(self, capsys: pytest.CaptureFixture[str]) -> None:
        meter = LLMUsageMeter()
        meter.record("advisor", "openai/gpt-5-mini", ChatUsage(prompt_tokens=12000, cost=Decimal("0.1234")))
        meter.record("advisor", "openai/gpt-5-mini", ChatUsage(prompt_tokens=1000, cost=Decimal("0.0100")))

        print_llm_usage(meter)

        output = capsys.readouterr().out
        assert "advisor" in output
        assert "openai/gpt-5-mini" in output
        assert "13,000" in output
        assert "$0.1334" in output
        assert "Total" in output


class TestSaveLLMUsage:
    async def test__no_meter__nothing_saved(self, user: User, mock_uow: mock.AsyncMock) -> None:
        await save_llm_usage(user_id=user.id, operation=LLMOperation.ENRICH, meter=None, uow=mock_uow)

        mock_uow.__aenter__.assert_not_awaited()

    async def test__failure__logged_not_raised(
        self,
        user: User,
        mock_uow: mock.AsyncMock,
        mock_llm_usage_repository: mock.AsyncMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        meter = LLMUsageMeter()
        spend(meter)
        mock_llm_usage_repository.add_many.side_effect = RuntimeError("database down")

        with caplog.at_level(logging.ERROR):
            await save_llm_usage(user_id=user.id, operation=LLMOperation.ENRICH, meter=meter, uow=mock_uow)

        (record,) = caplog.records
        assert record.getMessage() == "Failed to save the LLM usage"
        assert record.__dict__["user_id"] == str(user.id)
        assert record.__dict__["operation"] == "enrich"
        assert record.exc_info is not None
