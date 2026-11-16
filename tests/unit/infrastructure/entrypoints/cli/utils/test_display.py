import logging
from collections.abc import Iterable
from datetime import timedelta
from decimal import Decimal

import pytest
from rich.logging import RichHandler

from museflow.domain.enums import ReasoningEffort
from museflow.infrastructure.adapters.common.llm.schemas import ChatUsage
from museflow.infrastructure.adapters.common.llm.usage import LLMUsageMeter
from museflow.infrastructure.config.loggers.setup import LOGGER_MUSEFLOW
from museflow.infrastructure.entrypoints.cli.utils.display import has_rich_log_handler
from museflow.infrastructure.entrypoints.cli.utils.display import print_llm_usage
from museflow.infrastructure.entrypoints.cli.utils.display import print_playlist_outcome

from tests.unit.factories.entities.playlist import PlaylistFactory
from tests.unit.factories.entities.track import TrackFactory


class TestHasRichLogHandler:
    @pytest.fixture
    def rich_log_handler(self) -> Iterable[None]:
        logger = logging.getLogger(LOGGER_MUSEFLOW)
        handler = RichHandler()
        logger.addHandler(handler)
        yield
        logger.removeHandler(handler)

    @pytest.mark.usefixtures("rich_log_handler")
    def test__rich_log_handler(self) -> None:
        assert has_rich_log_handler() is True

    def test__other_log_handler(self) -> None:
        assert has_rich_log_handler() is False


class TestPrintLLMUsage:
    def test__no_call__prints_nothing(self, capsys: pytest.CaptureFixture[str]) -> None:
        print_llm_usage(LLMUsageMeter(), verbose=True)

        assert capsys.readouterr().out == ""

    def test__prints_each_step_and_the_total(self, capsys: pytest.CaptureFixture[str]) -> None:
        meter = LLMUsageMeter()
        usage = ChatUsage(prompt_tokens=12000, cost=Decimal("0.1234"))
        meter.record("advisor", "openai/gpt-5-mini", ReasoningEffort.LOW, usage, timedelta(seconds=50))
        meter.record(
            "advisor",
            "openai/gpt-5-mini",
            ReasoningEffort.LOW,
            ChatUsage(prompt_tokens=1000, cost=Decimal("0.0100")),
            timedelta(seconds=20),
        )

        print_llm_usage(meter, verbose=True)

        output = capsys.readouterr().out
        assert "advisor" in output
        assert "openai/gpt-5-mini" in output
        assert "13,000" in output
        assert "$0.1334" in output
        assert "Total" in output
        assert "1m10s" in output
        assert "Elapsed: " in output

    def test__prints_the_reasoning_effort(self, capsys: pytest.CaptureFixture[str]) -> None:
        meter = LLMUsageMeter()
        meter.record("enricher", "openai/gpt-5-mini", ReasoningEffort.MINIMAL, ChatUsage(), timedelta(seconds=1))

        print_llm_usage(meter, verbose=True)

        output = capsys.readouterr().out
        assert "Effort" in output
        assert "minimal" in output

    def test__not_verbose__one_line(self, capsys: pytest.CaptureFixture[str]) -> None:
        meter = LLMUsageMeter()
        meter.record(
            "advisor",
            "openai/gpt-5-mini",
            ReasoningEffort.LOW,
            ChatUsage(cost=Decimal("0.1234")),
            timedelta(seconds=5),
        )
        meter.record(
            "advisor",
            "openai/gpt-5-mini",
            ReasoningEffort.LOW,
            ChatUsage(cost=Decimal("0.0100")),
            timedelta(seconds=5),
        )

        print_llm_usage(meter, verbose=False)

        # Its own block: a blank line before
        output = capsys.readouterr().out
        assert output.startswith("\n2 LLM call(s) · $0.1334 · ")
        assert "Total" not in output


class TestPrintPlaylistOutcome:
    def test__playlist_created(self, capsys: pytest.CaptureFixture[str]) -> None:
        tracks = [TrackFactory.build(name="Neon Harbor", album_name=None), TrackFactory.build()]
        # Brackets in a name are text, not a style tag
        playlist = PlaylistFactory.build(name="[MF] - Friday night")

        print_playlist_outcome(tracks=tracks, playlist=playlist, target=2, hint="Try again.")

        output = capsys.readouterr().out
        assert "Neon Harbor" in output
        assert "✓ Playlist [MF] - Friday night · 2/2 tracks" in output
        assert f"View it: museflow playlist view {playlist.id}" in output
        assert "Try again." not in output

    def test__dry_run__under_target(self, capsys: pytest.CaptureFixture[str]) -> None:
        print_playlist_outcome(tracks=[TrackFactory.build()], playlist=None, target=3, hint="Try again.")

        output = capsys.readouterr().out
        assert "Dry run: no playlist created" in output
        assert "View it" not in output
        assert "Only 1/3 tracks found: Try again." in output
