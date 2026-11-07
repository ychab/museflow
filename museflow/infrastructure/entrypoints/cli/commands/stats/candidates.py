import asyncio

from pydantic import EmailStr

import typer
from rich.table import Table

from museflow.application.use_cases.stats_candidates import artist_candidates
from museflow.domain.enums import SourceFilter
from museflow.domain.exceptions import UserNotFound
from museflow.domain.value_objects.stats import ArtistCandidate
from museflow.infrastructure.entrypoints.cli.commands.stats import app
from museflow.infrastructure.entrypoints.cli.commands.stats import console
from museflow.infrastructure.entrypoints.cli.dependencies import get_unit_of_work
from museflow.infrastructure.entrypoints.cli.options import EMAIL_OPTION


@app.command("candidates", help="Show artists to explore: few total tracks but high average score.")
def stats_candidates(
    email: str = EMAIL_OPTION,
    limit: int = typer.Option(20, help="Max rows in the table"),
    source: SourceFilter = typer.Option(SourceFilter.ALL, "--source", help="Track source to include"),
    max_tracks: int = typer.Option(5, "--max-tracks", help="Maximum total tracks for an artist to be a candidate"),
    min_avg: float = typer.Option(7.0, "--min-avg", help="Minimum average score for an artist to be a candidate"),
) -> None:
    try:
        rows = asyncio.run(
            candidates_logic(
                email=email,
                limit=limit,
                source=source,
                max_tracks=max_tracks,
                min_avg=min_avg,
            )
        )
    except UserNotFound as e:
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


async def candidates_logic(
    email: EmailStr,
    limit: int,
    source: SourceFilter,
    max_tracks: int,
    min_avg: float,
) -> list[ArtistCandidate]:
    uow = get_unit_of_work()

    async with uow:
        user = await uow.users.get_by_email(email)

    if not user:
        raise UserNotFound()

    return await artist_candidates(
        user_id=user.id,
        source=source,
        max_tracks=max_tracks,
        min_avg=min_avg,
        limit=limit,
        uow=uow,
    )
