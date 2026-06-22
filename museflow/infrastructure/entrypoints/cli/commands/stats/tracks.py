import asyncio
from contextlib import AsyncExitStack
from typing import cast

from pydantic import EmailStr

import typer
from rich.table import Table

from museflow.domain.entities.track import Track
from museflow.domain.exceptions import UserNotFound
from museflow.infrastructure.entrypoints.cli.commands.stats import app
from museflow.infrastructure.entrypoints.cli.commands.stats import console
from museflow.infrastructure.entrypoints.cli.dependencies import get_db
from museflow.infrastructure.entrypoints.cli.dependencies import get_track_repository
from museflow.infrastructure.entrypoints.cli.dependencies import get_user_repository
from museflow.infrastructure.entrypoints.cli.parsers import parse_email
from museflow.infrastructure.entrypoints.cli.types import TrackSortBy


@app.command("tracks", help="Show top rated tracks.")
def stats_tracks(
    email: str = typer.Option(..., help="User email address", parser=parse_email),
    score_min: int | None = typer.Option(None, "--score-min", help="Minimum score filter (0-10)"),
    score_max: int | None = typer.Option(None, "--score-max", help="Maximum score filter (0-10)"),
    sort: TrackSortBy = typer.Option(TrackSortBy.SCORE, "--sort", help="Ranking strategy"),
    limit: int = typer.Option(20, help="Max rows in the table"),
) -> None:
    try:
        tracks = asyncio.run(
            tracks_logic(
                email=email,
                limit=limit,
                score_min=score_min,
                score_max=score_max,
                sort=sort,
            )
        )
    except UserNotFound as e:
        raise typer.BadParameter(f"User not found with email: {email}") from e
    except Exception as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e

    if not tracks:
        typer.secho("No rated tracks found.", fg=typer.colors.YELLOW)
        return

    table = Table(title="Top Tracks")
    table.add_column("#", justify="right", style="dim")
    table.add_column("Artist(s)")
    table.add_column("Track")
    table.add_column("Score", justify="center")
    table.add_column("Played", justify="center")
    for i, track in enumerate(tracks, start=1):
        table.add_row(str(i), ", ".join(track.artists), track.name, str(track.score), str(track.played_count))
    console.print(table)


async def tracks_logic(
    email: EmailStr,
    limit: int,
    score_min: int | None,
    score_max: int | None,
    sort: TrackSortBy,
) -> list[Track]:
    async with AsyncExitStack() as stack:
        session = await stack.enter_async_context(get_db())
        user_repository = get_user_repository(session)
        track_repository = get_track_repository(session)

        user = await user_repository.get_by_email(email)
        if not user:
            raise UserNotFound()

        tracks = await track_repository.get_list(
            user_id=user.id,
            min_score=score_min if score_min is not None else 0,
            max_score=score_max,
            limit=None,
        )
        if sort == TrackSortBy.PLAYED_COUNT:
            tracks.sort(key=lambda t: (-t.played_count, t.artists[0] if t.artists else ""))
        else:
            tracks.sort(key=lambda t: (-cast(int, t.score), t.artists[0] if t.artists else ""))

    return tracks[:limit]
