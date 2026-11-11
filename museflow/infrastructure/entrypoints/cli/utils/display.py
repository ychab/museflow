import logging
from contextlib import nullcontext
from datetime import timedelta

from rich import get_console
from rich.console import Console
from rich.logging import RichHandler
from rich.status import Status
from rich.table import Table

from museflow.domain.enums import RankingSortBy
from museflow.domain.value_objects.stats import RankableStats
from museflow.domain.value_objects.stats import Ranking
from museflow.infrastructure.adapters.common.llm.usage import LLMUsageMeter
from museflow.infrastructure.config.loggers import LOGGER_MUSEFLOW

console = Console()


def format_duration(duration: timedelta) -> str:
    """A short human duration: `8.4s`, `4m09s`, `1h02m`."""
    seconds = duration.total_seconds()
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes, seconds = divmod(int(seconds), 60)
    if minutes < 60:
        return f"{minutes}m{seconds:02d}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h{minutes:02d}m"


def spinner(message: str) -> Status | nullcontext[None]:
    """Shows a spinner with the `rich` log handler only: it shares Rich's console, so its logs print above the spinner."""
    if any(isinstance(handler, RichHandler) for handler in logging.getLogger(LOGGER_MUSEFLOW).handlers):
        return get_console().status(message)
    return nullcontext()


def build_ranking_table[S: RankableStats](
    title: str,
    label: str,
    rankings: list[Ranking[S]],
    sort: RankingSortBy,
) -> Table:
    """A ranking as `stats artists` and `stats tags` show it; the overall score only when it is the sort."""
    table = Table(title=title)
    table.add_column("#", justify="right", style="dim")
    table.add_column(label)
    table.add_column("Quality", justify="center")
    table.add_column("Rate Avg", justify="center")
    table.add_column("Rated", justify="right")
    table.add_column("Tracks", justify="right")
    table.add_column("Played", justify="right")
    if sort == RankingSortBy.OVERALL:
        table.add_column("Overall", justify="center")

    for i, ranking in enumerate(rankings, start=1):
        cells = [
            str(i),
            ranking.stats.name,
            f"{ranking.quality_score:.1f}" if ranking.quality_score is not None else "—",
            f"{ranking.rate_avg:.1f}" if ranking.rate_avg is not None else "—",
            str(ranking.stats.rated_count),
            str(ranking.stats.track_count),
            str(ranking.stats.plays_count),
        ]
        if sort == RankingSortBy.OVERALL:
            cells.append(f"{ranking.overall_score:.1f}")
        table.add_row(*cells)

    return table


def print_llm_usage(meter: LLMUsageMeter) -> None:
    """Prints what the command spent on LLM calls, per step and model, then how long it ran.

    Prints nothing when no call was made.
    """
    usages = meter.usages
    if not usages:
        return

    table = Table(title="LLM usage", show_footer=True)
    table.add_column("Step", footer="Total")
    table.add_column("Model")
    table.add_column("Calls", justify="right", footer=str(sum(usage.calls for usage in usages)))
    table.add_column("Prompt", justify="right", footer=f"{sum(usage.prompt_tokens for usage in usages):,}")
    table.add_column("Completion", justify="right", footer=f"{sum(usage.completion_tokens for usage in usages):,}")
    table.add_column("Reasoning", justify="right", footer=f"{sum(usage.reasoning_tokens for usage in usages):,}")
    table.add_column("Cost", justify="right", footer=f"${meter.total_cost:.4f}")
    table.add_column("Time", justify="right", footer=format_duration(sum((u.duration for u in usages), timedelta(0))))
    for usage in usages:
        table.add_row(
            usage.step,
            usage.model,
            str(usage.calls),
            f"{usage.prompt_tokens:,}",
            f"{usage.completion_tokens:,}",
            f"{usage.reasoning_tokens:,}",
            f"${usage.cost:.4f}",
            format_duration(usage.duration),
        )
    console.print(table)
    # Wall-clock time: the LLM calls, plus the database work and the throttling sleeps
    console.print(f"Elapsed: {format_duration(meter.elapsed)}")
