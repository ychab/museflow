from decimal import Decimal
from io import StringIO

import pytest
from rich.console import Console

from museflow.infrastructure.adapters.common.llm.schemas import ChatUsage
from museflow.infrastructure.adapters.common.llm.usage import LLMUsageMeter
from museflow.infrastructure.entrypoints.cli import utils
from museflow.infrastructure.entrypoints.cli.utils import print_llm_usage
from museflow.infrastructure.entrypoints.cli.utils import working


class TestWorking:
    @pytest.mark.parametrize("terminal", [True, False])
    def test__shows_spinner_only_on_terminal(self, terminal: bool, monkeypatch: pytest.MonkeyPatch) -> None:
        output = StringIO()
        monkeypatch.setenv("TERM", "xterm")
        console = Console(file=output, force_terminal=terminal, width=80)
        monkeypatch.setattr(utils, "get_console", lambda: console)

        with working("Working on the test"):
            console.print("command output")

        rendered = output.getvalue()
        assert "command output" in rendered
        assert ("Working on the test" in rendered) is terminal


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
