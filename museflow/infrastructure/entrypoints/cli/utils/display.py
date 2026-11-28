import logging
from datetime import timedelta

from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table
from rich.text import Text

from museflow.application.outputs.stats import RankableStats
from museflow.application.outputs.stats import Ranking
from museflow.domain.entities.playlist import Playlist
from museflow.domain.entities.track import Track
from museflow.domain.enums import RankingSortBy
from museflow.infrastructure.adapters.common.llm.usage import LLMUsageMeter
from museflow.infrastructure.config.loggers.setup import LOGGER_MUSEFLOW
from museflow.infrastructure.utils.formatting import format_duration

console = Console()


def has_rich_log_handler() -> bool:
    """Whether the logs print through the `rich` handler: a live line (spinner, progress) on its console is safe then.

    Another handler writes to the stream directly, which would break the live line.
    """
    return any(isinstance(handler, RichHandler) for handler in logging.getLogger(LOGGER_MUSEFLOW).handlers)


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


def print_playlist_outcome(tracks: list[Track], playlist: Playlist | None, target: int, hint: str) -> None:
    """Prints the tracks of a generated playlist, then where to find it, or that the dry run created none.

    When fewer tracks than the `target` were found, a warning ends with the `hint` on how to find more.
    """
    table = Table(box=None, header_style="bold dim", pad_edge=False)
    table.add_column("#", justify="right", style="dim")
    table.add_column("Artist(s)")
    table.add_column("Track")
    table.add_column("Album", style="dim")

    for i, track in enumerate(tracks, start=1):
        table.add_row(str(i), ", ".join(track.artists), track.name, track.album_name or "")

    console.print(table)
    console.print()

    # Text, not markup: a playlist name like "[MF] - …" would be read as a style tag.
    if playlist is None:
        console.print(Text.assemble(("! ", "bold yellow"), ("Dry run: no playlist created", "yellow")))
    else:
        console.print(
            Text.assemble(
                ("✓ ", "green"),
                ("Playlist ", "bold"),
                (playlist.name, "bold green"),
                f" · {len(tracks)}/{target} tracks",
            )
        )
        console.print(Text(f"  View it: museflow playlist view {playlist.id}", style="cyan"))
        console.print(Text("  Rate tracks: museflow rate playlist --play", style="cyan"))

    if len(tracks) < target:
        console.print(
            Text.assemble(("! ", "bold yellow"), (f"Only {len(tracks)}/{target} tracks found: ", "yellow"), hint)
        )


def print_llm_usage(meter: LLMUsageMeter, verbose: bool) -> None:
    """Prints what the command spent on LLM calls and how long it ran: one line, or a table per step and model.

    Prints nothing when no call was made.
    """
    usages = meter.run_usages
    if not usages:
        return

    # Its own block, after the results or the error
    console.print()
    if not verbose:
        calls = sum(usage.calls for usage in usages)
        console.print(f"{calls} LLM call(s) · ${meter.total_cost:.4f} · {format_duration(meter.elapsed)}")
        return

    table = Table(title="LLM usage", show_footer=True)
    table.add_column("Step", footer="Total")
    table.add_column("Model")
    table.add_column("Effort")
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
            usage.reasoning_effort,
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
