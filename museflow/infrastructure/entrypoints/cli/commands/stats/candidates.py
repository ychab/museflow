from typing import Annotated

from pydantic import EmailStr

import typer
from rich.table import Table

from museflow.application.outputs.stats import ArtistCandidate
from museflow.application.use_cases.stats_artist_candidates_get import get_artist_candidates
from museflow.application.use_cases.user_get import get_user
from museflow.domain.enums import SourceFilter
from museflow.domain.exceptions import UserNotFoundError
from museflow.infrastructure.entrypoints.cli.commands.stats import app
from museflow.infrastructure.entrypoints.cli.commands.stats import console
from museflow.infrastructure.entrypoints.cli.dependencies import get_wiring
from museflow.infrastructure.entrypoints.cli.dependencies import run_logic
from museflow.infrastructure.entrypoints.cli.options import EmailOption


@app.command("candidates", help="Show artists to explore: few total tracks but high average score.")
def stats_candidates_command(
    email: EmailOption,
    limit: Annotated[int, typer.Option(help="Max rows in the table")] = 20,
    source: Annotated[SourceFilter, typer.Option("--source", help="Track source to include")] = SourceFilter.ALL,
    max_tracks: Annotated[
        int, typer.Option("--max-tracks", help="Maximum total tracks for an artist to be a candidate")
    ] = 5,
    min_avg: Annotated[
        float, typer.Option("--min-avg", help="Minimum average score for an artist to be a candidate")
    ] = 7.0,
) -> None:
    try:
        rows = run_logic(
            stats_candidates_logic(
                email=email,
                limit=limit,
                source=source,
                max_tracks=max_tracks,
                min_avg=min_avg,
            )
        )
    except UserNotFoundError as e:
        raise typer.BadParameter(f"User not found with email: {email}") from e
    except Exception as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e

    if not rows:
        typer.secho("No discovery candidates found.", fg=typer.colors.YELLOW)
        return

    table = Table(title="Discovery Candidates")
    table.add_column("#", justify="right", style="dim")
    table.add_column("Artist")
    table.add_column("Avg Score", justify="center")
    table.add_column("Rated", justify="right")
    table.add_column("Total", justify="right")
    for i, row in enumerate(rows, start=1):
        table.add_row(
            str(i),
            row.artist,
            f"{row.avg_score:.1f}",
            str(row.rated_count),
            str(row.total_count),
        )
    console.print(table)


async def stats_candidates_logic(
    email: EmailStr,
    limit: int,
    source: SourceFilter,
    max_tracks: int,
    min_avg: float,
) -> list[ArtistCandidate]:
    uow = get_wiring().build_unit_of_work()

    user = await get_user(email=email, uow=uow)

    return await get_artist_candidates(
        user_id=user.id,
        source=source,
        max_tracks=max_tracks,
        min_avg=min_avg,
        limit=limit,
        uow=uow,
    )
