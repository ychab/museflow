import asyncio
import math
from collections import defaultdict
from contextlib import AsyncExitStack
from dataclasses import dataclass
from typing import cast

from pydantic import EmailStr

import typer
from rich.table import Table

from museflow.domain.entities.music import Track
from museflow.domain.exceptions import UserNotFound
from museflow.infrastructure.config.settings.app import app_settings
from museflow.infrastructure.entrypoints.cli.commands.stats import app
from museflow.infrastructure.entrypoints.cli.commands.stats import console
from museflow.infrastructure.entrypoints.cli.dependencies import get_db
from museflow.infrastructure.entrypoints.cli.dependencies import get_track_repository
from museflow.infrastructure.entrypoints.cli.dependencies import get_user_repository
from museflow.infrastructure.entrypoints.cli.parsers import parse_email
from museflow.infrastructure.entrypoints.cli.types import ArtistSortBy
from museflow.infrastructure.entrypoints.cli.types import SourceFilter


@dataclass(frozen=True, kw_only=True)
class ArtistRow:
    artist: str
    quality_score: float | None  # None for artists with no rated tracks
    overall_score: float
    rate_avg: float | None  # None for artists with no rated tracks
    rated_count: int
    track_count: int
    plays_count: int


@app.command("artists", help="Show top artists ranked by overall score (breadth x depth x quality).")
def stats_artists(
    email: str = typer.Option(..., help="User email address", parser=parse_email),
    source: SourceFilter = typer.Option(SourceFilter.ALL, "--source", help="Track source to include"),
    score_min: int | None = typer.Option(None, "--score-min", help="Minimum score filter (0-10)"),
    score_max: int | None = typer.Option(None, "--score-max", help="Maximum score filter (0-10)"),
    confidence: int = typer.Option(
        app_settings.STATS_BAYESIAN_CONFIDENCE,
        "--confidence",
        help="Bayesian confidence constant: artists with fewer rated tracks than this are pulled toward the mean",
    ),
    sort: ArtistSortBy = typer.Option(ArtistSortBy.OVERALL, "--sort", help="Ranking strategy"),
    limit: int = typer.Option(20, help="Max rows in the table"),
) -> None:
    try:
        rows = asyncio.run(
            artists_logic(
                email=email,
                limit=limit,
                source=source,
                score_min=score_min,
                score_max=score_max,
                confidence=confidence,
                sort=sort,
            )
        )
    except UserNotFound as e:
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


def _is_in_score_range(score: int | None, score_min: int | None, score_max: int | None) -> bool:
    if score is None:
        return False
    if score_min is not None and score < score_min:
        return False
    if score_max is not None and score > score_max:
        return False
    return True


async def artists_logic(
    email: EmailStr,
    limit: int,
    source: SourceFilter,
    score_min: int | None,
    score_max: int | None,
    confidence: int,
    sort: ArtistSortBy,
) -> list[ArtistRow]:
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

    all_rated_scores = [cast(int, t.score) for t in all_tracks if _is_in_score_range(t.score, score_min, score_max)]
    global_mean = sum(all_rated_scores) / len(all_rated_scores) if all_rated_scores else 0.0

    rows: list[ArtistRow] = []
    for artist, tracks in artist_tracks.items():
        rated_scores = [cast(int, t.score) for t in tracks if _is_in_score_range(t.score, score_min, score_max)]
        rated_count = len(rated_scores)
        track_count = len(tracks)
        plays_count = sum(t.played_count for t in tracks)

        rate_avg: float | None
        quality_score: float | None
        if rated_count > 0:
            rate_avg = sum(rated_scores) / rated_count
            quality = (confidence * global_mean + rated_count * rate_avg) / (confidence + rated_count)
            quality_score = quality
        else:
            rate_avg = None
            quality = global_mean
            quality_score = None

        quality_ratio = quality / global_mean if global_mean > 0 else 1.0
        overall_score = math.log(1 + track_count) * math.log(1 + plays_count) * quality_ratio

        rows.append(
            ArtistRow(
                artist=artist,
                quality_score=quality_score,
                overall_score=overall_score,
                rate_avg=rate_avg,
                rated_count=rated_count,
                track_count=track_count,
                plays_count=plays_count,
            )
        )

    if sort == ArtistSortBy.TRACK_COUNT:
        rows.sort(key=lambda r: (-r.track_count, r.artist))
    elif sort == ArtistSortBy.PLAYS_COUNT:
        rows.sort(key=lambda r: (-r.plays_count, r.artist))
    elif sort == ArtistSortBy.RATE_AVG:
        rows.sort(key=lambda r: (-(r.rate_avg or 0.0), r.artist))
    elif sort == ArtistSortBy.QUALITY:
        rows.sort(key=lambda r: (-(r.quality_score or 0.0), r.artist))
    else:
        rows.sort(key=lambda r: (-r.overall_score, r.artist))

    return rows[:limit]
