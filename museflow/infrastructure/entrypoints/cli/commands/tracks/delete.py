import asyncio
from contextlib import AsyncExitStack
from dataclasses import dataclass

from pydantic import EmailStr

import typer

from museflow.domain.exceptions import UserNotFound
from museflow.domain.types import MusicProvider
from museflow.domain.types import TrackSource
from museflow.infrastructure.entrypoints.cli.commands.tracks import app
from museflow.infrastructure.entrypoints.cli.dependencies import get_db
from museflow.infrastructure.entrypoints.cli.dependencies import get_track_repository
from museflow.infrastructure.entrypoints.cli.dependencies import get_user_repository
from museflow.infrastructure.entrypoints.cli.parsers import parse_email
from museflow.infrastructure.entrypoints.cli.types import SourceFilter


@dataclass(frozen=True, kw_only=True)
class TracksDeleteResult:
    no_tracks: bool = False
    deleted_count: int = 0


@app.command("delete", help="Delete tracks matching the given filters.")
def delete(
    email: str = typer.Option(..., help="User email address", parser=parse_email),
    artist: str | None = typer.Option(None, "--artist", help="Filter by primary artist name (case-insensitive)"),
    name: str | None = typer.Option(None, "--name", help="Filter by track name (case-insensitive)"),
    source: SourceFilter = typer.Option(SourceFilter.ALL, "--source", help="Filter by track source"),
    provider: MusicProvider | None = typer.Option(None, "--provider", help="Filter by music provider"),
    purge: bool = typer.Option(False, "--purge", help="Delete all tracks without artist/name filter"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
) -> None:
    if not purge and not artist and not name:
        raise typer.BadParameter("Provide at least --artist or --name, or use --purge to delete all tracks.")

    try:
        result = asyncio.run(
            delete_logic(
                email=email,
                artist=artist,
                name=name,
                source=source.to_track_source(),
                provider=provider,
                purge=purge,
                yes=yes,
            )
        )
    except UserNotFound as e:
        raise typer.BadParameter(f"User not found with email: {email}") from e
    except Exception as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e

    if result.no_tracks:
        typer.secho("No tracks found matching the filters.", fg=typer.colors.YELLOW)
        return

    typer.secho(f"Deleted {result.deleted_count} track(s).", fg=typer.colors.GREEN)


async def delete_logic(
    email: EmailStr,
    artist: str | None,
    name: str | None,
    source: TrackSource | None,
    provider: MusicProvider | None,
    purge: bool = False,
    yes: bool = False,
) -> TracksDeleteResult:
    async with AsyncExitStack() as stack:
        session = await stack.enter_async_context(get_db())

        user = await get_user_repository(session).get_by_email(email)
        if not user:
            raise UserNotFound()

        track_repository = get_track_repository(session)

        tracks = await track_repository.get_list(
            user_id=user.id,
            artist_name=artist,
            source=source,
            provider=provider,
        )
        if name is not None:
            tracks = [t for t in tracks if t.name.lower() == name.lower()]

        count = len(tracks)
        if count == 0:
            return TracksDeleteResult(no_tracks=True)

        if artist and not name and not purge:
            for track in sorted(tracks, key=lambda t: t.name):
                typer.echo(f"  {track.name}")

        if not yes:
            typer.confirm(f"About to delete {count} track(s). Continue?", abort=True)

        deleted = await track_repository.delete(
            user_id=user.id,
            artist_name=artist,
            track_name=name,
            source=source,
            provider=provider,
        )
        return TracksDeleteResult(deleted_count=deleted)
