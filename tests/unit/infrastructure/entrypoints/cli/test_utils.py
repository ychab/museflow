from decimal import Decimal

import pytest

from museflow.infrastructure.adapters.common.llm.schemas import ChatUsage
from museflow.infrastructure.adapters.common.llm.usage import LLMUsageMeter
from museflow.infrastructure.entrypoints.cli.utils import print_llm_usage


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
