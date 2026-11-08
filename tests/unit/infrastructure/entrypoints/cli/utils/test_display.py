import logging
from collections.abc import Iterable
from contextlib import nullcontext
from datetime import timedelta
from decimal import Decimal

import pytest
from rich.logging import RichHandler
from rich.status import Status

from museflow.infrastructure.adapters.common.llm.schemas import ChatUsage
from museflow.infrastructure.adapters.common.llm.usage import LLMUsageMeter
from museflow.infrastructure.config.loggers import LOGGER_MUSEFLOW
from museflow.infrastructure.entrypoints.cli.utils.display import format_duration
from museflow.infrastructure.entrypoints.cli.utils.display import print_llm_usage
from museflow.infrastructure.entrypoints.cli.utils.display import spinner


class TestSpinner:
    @pytest.fixture
    def rich_log_handler(self) -> Iterable[None]:
        logger = logging.getLogger(LOGGER_MUSEFLOW)
        handler = RichHandler()
        logger.addHandler(handler)
        yield
        logger.removeHandler(handler)

    @pytest.mark.usefixtures("rich_log_handler")
    def test__rich_log_handler(self) -> None:
        assert isinstance(spinner("Working"), Status)

    def test__other_log_handler(self) -> None:
        assert isinstance(spinner("Working"), nullcontext)


class TestPrintLLMUsage:
    def test__no_call__prints_nothing(self, capsys: pytest.CaptureFixture[str]) -> None:
        print_llm_usage(LLMUsageMeter())

        assert capsys.readouterr().out == ""

    def test__prints_each_step_and_the_total(self, capsys: pytest.CaptureFixture[str]) -> None:
        meter = LLMUsageMeter()
        usage = ChatUsage(prompt_tokens=12000, cost=Decimal("0.1234"))
        meter.record("advisor", "openai/gpt-5-mini", usage, timedelta(seconds=50))
        meter.record(
            "advisor",
            "openai/gpt-5-mini",
            ChatUsage(prompt_tokens=1000, cost=Decimal("0.0100")),
            timedelta(seconds=20),
        )

        print_llm_usage(meter)

        output = capsys.readouterr().out
        assert "advisor" in output
        assert "openai/gpt-5-mini" in output
        assert "13,000" in output
        assert "$0.1334" in output
        assert "Total" in output
        assert "1m10s" in output
        assert "Elapsed: " in output


class TestFormatDuration:
    @pytest.mark.parametrize(
        ("seconds", "expected"),
        [(8.43, "8.4s"), (249, "4m09s"), (3725, "1h02m")],
    )
    def test__nominal(self, seconds: float, expected: str) -> None:
        assert format_duration(timedelta(seconds=seconds)) == expected
