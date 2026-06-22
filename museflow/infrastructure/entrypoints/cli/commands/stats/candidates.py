import asyncio
from collections import defaultdict
from contextlib import AsyncExitStack
from dataclasses import dataclass
from typing import cast

from pydantic import EmailStr

import typer
from rich.table import Table

from museflow.domain.entities.track import Track
from museflow.domain.exceptions import UserNotFound
from museflow.infrastructure.entrypoints.cli.commands.stats import SourceFilter
from museflow.infrastructure.entrypoints.cli.commands.stats import app
from museflow.infrastructure.entrypoints.cli.commands.stats import console
from museflow.infrastructure.entrypoints.cli.dependencies import get_db
from museflow.infrastructure.entrypoints.cli.dependencies import get_track_repository
from museflow.infrastructure.entrypoints.cli.dependencies import get_user_repository
from museflow.infrastructure.entrypoints.cli.parsers import parse_email


@dataclass(frozen=True, kw_only=True)
class CandidateRow:
    artist: str
    avg_score: float
    rated_count: int
    total_count: int


@app.command("candidates", help="Show artists to explore: few total tracks but high average score.")
def stats_candidates(
    email: str = typer.Option(..., help="User email address", parser=parse_email),
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
) -> list[CandidateRow]:
    async with AsyncExitStack() as stack:
        session = await stack.enter_async_context(get_db())
        user_repository = get_user_repository(session)
        track_repository = get_track_repository(session)

        user = await user_repository.get_by_email(email)
        if not user:
            raise UserNotFound()

        all_tracks = await track_repository.get_list(
            user_id=user.id,
            source=source.to_track_source(),
            limit=None,
        )

    artist_tracks: dict[str, list[Track]] = defaultdict(list)
    for track in all_tracks:
        artist_tracks[track.primary_artist].append(track)

    rows: list[CandidateRow] = []
    for artist, tracks in artist_tracks.items():
        total_count = len(tracks)
        if total_count > max_tracks:
            continue

        rated_scores = [cast(int, t.score) for t in tracks if t.score is not None]
        rated_count = len(rated_scores)
        if rated_count == 0:
            continue

        avg_score = sum(rated_scores) / rated_count
        if avg_score < min_avg:
            continue

        rows.append(
            CandidateRow(
                artist=artist,
                avg_score=avg_score,
                rated_count=rated_count,
                total_count=total_count,
            )
        )

    rows.sort(key=lambda r: (-r.avg_score, r.artist))
    return rows[:limit]
