import time
from datetime import timedelta
from decimal import Decimal
from types import TracebackType
from typing import Final
from typing import Self

from rich.console import Console
from rich.status import Status
from rich.table import Table
from rich.text import Text

from museflow.application.ports.progress import ProgressPort
from museflow.domain.enums import ProgressStep
from museflow.domain.value_objects.progress import CandidatesFound
from museflow.domain.value_objects.progress import PicksMade
from museflow.domain.value_objects.progress import ProgressEvent
from museflow.domain.value_objects.progress import StepStarted
from museflow.domain.value_objects.progress import StrategyChosen
from museflow.infrastructure.adapters.common.duration import format_duration
from museflow.infrastructure.adapters.common.llm.usage import LLMUsageMeter


class RichProgressAdapter(ProgressPort):
    """Prints one line per finished step on a Rich console, under a live status line naming the step running.

    Used as a context manager, which starts and stops the live status. Without `animated` (logs printed by another
    handler would break the live line), only the finished steps print.
    """

    _RUNNING_LABELS: Final[dict[ProgressStep, str]] = {
        ProgressStep.DISCOVERY_ARTISTS: "Suggesting artists…",
        ProgressStep.DISCOVERY_SEARCH: "Searching the catalogue…",
        ProgressStep.DISCOVERY_PICKS: "Picking tracks…",
        ProgressStep.PLAYLIST_CREATE: "Creating the playlist…",
    }

    def __init__(self, console: Console, meter: LLMUsageMeter | None = None, animated: bool = True) -> None:
        self._console = console
        self._meter = meter
        self._animated = animated
        self._status: Status | None = None
        self._attempt: int | None = None
        # The step running: when it started and what had been spent by then
        self._started_at = time.monotonic()
        self._cost_before = Decimal(0)

    def __enter__(self) -> Self:
        if self._animated:
            self._status = self._console.status("Starting…")
            self._status.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._status is not None:
            self._status.stop()
            self._status = None

    async def publish(self, event: ProgressEvent) -> None:
        if isinstance(event, StepStarted):
            self._start(event)
        elif isinstance(event, StrategyChosen):
            self._print_done("Artists suggested", f"{len(event.strategy.artists)} · {event.strategy.strategy_label}")
        elif isinstance(event, CandidatesFound):
            self._print_done(
                "Catalogue searched", f"{event.tracks} unknown track(s) · {event.artists_kept}/{event.artists} artists"
            )
        elif isinstance(event, PicksMade):
            self._print_done("Tracks picked", f"{len(event.picks)} → {event.kept}/{event.target} kept")
        else:
            self._print_done("Playlist created", f"{len(event.playlist.tracks)} track(s)")

    def _start(self, event: StepStarted) -> None:
        if event.attempt is not None and event.attempt != self._attempt:
            self._attempt = event.attempt
            of = f"/{event.max_attempts}" if event.max_attempts is not None else ""
            self._console.print(Text(f"Attempt {event.attempt}{of}", style="bold"))
        if self._status is not None:
            self._status.update(self._RUNNING_LABELS[event.step])
        self._started_at = time.monotonic()
        self._cost_before = self._spent()

    def _print_done(self, label: str, detail: str) -> None:
        timing = format_duration(timedelta(seconds=time.monotonic() - self._started_at))
        if cost := self._spent() - self._cost_before:
            timing += f" · ${cost:.4f}"

        line = Table.grid(padding=(0, 1), expand=True)
        line.add_column(width=2)
        line.add_column(width=19)
        line.add_column(ratio=1)
        line.add_column(justify="right", style="dim")
        line.add_row(Text(" ✓", style="green"), label, detail, timing)
        self._console.print(line)

    def _spent(self) -> Decimal:
        return self._meter.total_cost if self._meter is not None else Decimal(0)
