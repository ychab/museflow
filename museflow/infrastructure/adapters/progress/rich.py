import time
from datetime import timedelta
from decimal import Decimal
from types import TracebackType
from typing import Final
from typing import Self

from rich.console import Console
from rich.console import RenderableType
from rich.progress import BarColumn
from rich.progress import MofNCompleteColumn
from rich.progress import Progress
from rich.progress import ProgressColumn
from rich.progress import SpinnerColumn
from rich.progress import Task
from rich.progress import TaskID
from rich.progress import TextColumn
from rich.progress import TimeElapsedColumn
from rich.progress import TimeRemainingColumn
from rich.table import Table
from rich.text import Text

from museflow.application.ports.progress import ProgressPort
from museflow.domain.enums import ProgressStep
from museflow.domain.value_objects.progress import CandidatesFound
from museflow.domain.value_objects.progress import PicksMade
from museflow.domain.value_objects.progress import ProgressEvent
from museflow.domain.value_objects.progress import StepAdvanced
from museflow.domain.value_objects.progress import StepDone
from museflow.domain.value_objects.progress import StepStarted
from museflow.domain.value_objects.progress import StrategyChosen
from museflow.infrastructure.adapters.common.llm.usage import LLMUsageMeter
from museflow.infrastructure.utils.formatting import format_duration


class RichProgressAdapter(ProgressPort):
    """Prints one line per finished step on a Rich console, under a live line for the step running.

    The live line shows a spinner and the step's label, plus a bar, a count and the time left for a step that goes
    through a known number of units. Used as a context manager, which starts and stops the live line. Without
    `animated` (logs printed by another handler would break the live line), only the finished steps print.
    """

    _RUNNING_LABELS: Final[dict[ProgressStep, str]] = {
        ProgressStep.DISCOVERY_ARTISTS: "Suggesting artists…",
        ProgressStep.DISCOVERY_SEARCH: "Searching the catalogue…",
        ProgressStep.DISCOVERY_PICKS: "Picking tracks…",
        ProgressStep.PLAYLIST_CREATE: "Creating the playlist…",
        ProgressStep.ENRICH_TRACKS: "Enriching tracks…",
        ProgressStep.TASTE_PERIODS: "Profiling the listening periods…",
        ProgressStep.TASTE_REFLECT: "Reflecting on the profile…",
        ProgressStep.HISTORY_READ: "Reading the history files…",
        ProgressStep.HISTORY_SAVE: "Saving tracks and plays…",
    }
    # The steps that end with StepDone, as their finished line names them, and the unit of their total
    _DONE_LABELS: Final[dict[ProgressStep, tuple[str, str]]] = {
        ProgressStep.ENRICH_TRACKS: ("Tracks enriched", "track(s)"),
        ProgressStep.TASTE_PERIODS: ("Periods profiled", "period(s)"),
        ProgressStep.TASTE_REFLECT: ("Profile reflected", ""),
        ProgressStep.HISTORY_READ: ("Files read", "file(s)"),
        ProgressStep.HISTORY_SAVE: ("Tracks saved", "track(s)"),
    }

    def __init__(self, console: Console, meter: LLMUsageMeter | None = None, animated: bool = True) -> None:
        self._console = console
        self._meter = meter
        self._animated = animated
        self._progress: Progress | None = None
        self._task: TaskID | None = None
        self._attempt: int | None = None
        # The step running: when it started, what had been spent by then, and the units it goes through
        self._started_at = time.monotonic()
        self._cost_before = Decimal(0)
        self._total: int | None = None

    def __enter__(self) -> Self:
        if self._animated:
            self._progress = Progress(
                SpinnerColumn(),
                TextColumn("{task.description}"),
                _WithTotalOnly(BarColumn()),
                _WithTotalOnly(MofNCompleteColumn()),
                TimeElapsedColumn(),
                _WithTotalOnly(TimeRemainingColumn()),
                console=self._console,
                transient=True,
            )
            self._progress.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._progress is not None:
            self._progress.stop()
            self._progress = None

    async def publish(self, event: ProgressEvent) -> None:
        if isinstance(event, StepStarted):
            self._start(event)
        elif isinstance(event, StepAdvanced):
            if self._progress is not None and self._task is not None:
                self._progress.update(self._task, completed=event.done, total=event.total)
        elif isinstance(event, StepDone):
            label, unit = self._DONE_LABELS[event.step]
            self._print_done(label, f"{self._total:,} {unit}" if self._total is not None else "")
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
        if self._progress is not None:
            self._remove_task()
            self._task = self._progress.add_task(self._RUNNING_LABELS[event.step], total=event.total)
        self._started_at = time.monotonic()
        self._cost_before = self._spent()
        self._total = event.total

    def _print_done(self, label: str, detail: str) -> None:
        self._remove_task()
        timing = format_duration(timedelta(seconds=time.monotonic() - self._started_at))
        if cost := self._spent() - self._cost_before:
            timing += f" · ${cost:.4f}"

        line = Table.grid(padding=(0, 1), expand=True)
        line.add_column(width=2)
        line.add_column(width=19)
        line.add_column(ratio=1)
        line.add_column(justify="right", style="dim")
        line.add_row(Text(" ✓", style="green"), label, detail, timing)
        # Printed above the live line, which the console keeps at the bottom
        self._console.print(line)

    def _remove_task(self) -> None:
        if self._progress is not None and self._task is not None:
            self._progress.remove_task(self._task)
        self._task = None

    def _spent(self) -> Decimal:
        return self._meter.total_cost if self._meter is not None else Decimal(0)


class _WithTotalOnly(ProgressColumn):
    """Renders the wrapped column for a task with a known total only: a single call has no bar, count or time left."""

    def __init__(self, column: ProgressColumn) -> None:
        super().__init__()
        self._column = column

    def render(self, task: Task) -> RenderableType:
        return self._column.render(task) if task.total is not None else Text("")
