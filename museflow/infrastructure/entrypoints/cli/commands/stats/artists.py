import asyncio

from pydantic import EmailStr

import typer
from rich.table import Table

from museflow.application.use_cases.stats_artists import list_top_artists
from museflow.domain.const import DISCOVERY_TRACK_SCORE_MAX
from museflow.domain.const import DISCOVERY_TRACK_SCORE_MIN
from museflow.domain.enums import ArtistSortBy
from museflow.domain.enums import SourceFilter
from museflow.domain.exceptions import UserNotFoundError
from museflow.domain.value_objects.stats import ArtistStats
from museflow.infrastructure.config.settings.app import app_settings
from museflow.infrastructure.entrypoints.cli.commands.stats import app
from museflow.infrastructure.entrypoints.cli.commands.stats import console
from museflow.infrastructure.entrypoints.cli.dependencies import get_unit_of_work
from museflow.infrastructure.entrypoints.cli.options import EMAIL_OPTION
from museflow.infrastructure.entrypoints.cli.parsers import validate_score_range


@app.command("artists", help="Show top artists ranked by overall score (breadth x depth x quality).")
def stats_artists_command(
    email: str = EMAIL_OPTION,
    source: SourceFilter = typer.Option(SourceFilter.ALL, "--source", help="Track source to include"),
    score_min: int | None = typer.Option(
        None,
        "--score-min",
        help="Minimum score filter (0-10)",
        min=DISCOVERY_TRACK_SCORE_MIN,
        max=DISCOVERY_TRACK_SCORE_MAX,
    ),
    score_max: int | None = typer.Option(
        None,
        "--score-max",
        help="Maximum score filter (0-10)",
        min=DISCOVERY_TRACK_SCORE_MIN,
        max=DISCOVERY_TRACK_SCORE_MAX,
    ),
    confidence: int = typer.Option(
        app_settings.STATS_BAYESIAN_CONFIDENCE,
        "--confidence",
        help="Bayesian confidence constant: artists with fewer rated tracks than this are pulled toward the mean",
    ),
    sort: ArtistSortBy = typer.Option(ArtistSortBy.OVERALL, "--sort", help="Ranking strategy"),
    limit: int = typer.Option(20, help="Max rows in the table", min=1),
) -> None:
    validate_score_range(score_min, score_max)

    try:
        rows = asyncio.run(
            stats_artists_logic(
                email=email,
                limit=limit,
                source=source,
                score_min=score_min,
                score_max=score_max,
                confidence=confidence,
                sort=sort,
            )
        )
    except UserNotFoundError as e:
        raise typer.BadParameter(f"User not found with email: {email}") from e
    except Exception as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e

    if not rows:
        typer.secho("No artist stats found.", fg=typer.colors.YELLOW)
        return

    table = Table(title="Top Artists")
    table.add_column("#", justify="right", style="dim")
    table.add_column("Artist")
    table.add_column("Quality", justify="center")
    table.add_column("Rate Avg", justify="center")
    table.add_column("Rated", justify="right")
    table.add_column("Tracks", justify="right")
    table.add_column("Played", justify="right")
    if sort == ArtistSortBy.OVERALL:
        table.add_column("Overall", justify="center")

    for i, row in enumerate(rows, start=1):
        cells = [
            str(i),
            row.artist,
            f"{row.quality_score:.1f}" if row.quality_score is not None else "—",
            f"{row.rate_avg:.1f}" if row.rate_avg is not None else "—",
            str(row.rated_count),
            str(row.track_count),
            str(row.plays_count),
        ]
        if sort == ArtistSortBy.OVERALL:
            cells.append(f"{row.overall_score:.1f}")

        table.add_row(*cells)

    console.print(table)


async def stats_artists_logic(
    email: EmailStr,
    limit: int,
    source: SourceFilter,
    score_min: int | None,
    score_max: int | None,
    confidence: int,
    sort: ArtistSortBy,
) -> list[ArtistStats]:
    uow = get_unit_of_work()

    async with uow:
        user = await uow.users.get_by_email(email)

    if not user:
        raise UserNotFoundError()

    return await list_top_artists(
        user_id=user.id,
        source=source,
        score_min=score_min,
        score_max=score_max,
        confidence=confidence,
        sort=sort,
        limit=limit,
        uow=uow,
    )
