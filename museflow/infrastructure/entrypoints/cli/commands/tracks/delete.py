import asyncio
from dataclasses import dataclass

from pydantic import EmailStr

import typer

from museflow.application.use_cases.tracks_delete import TracksDeleteUseCase
from museflow.domain.enums import MusicProvider
from museflow.domain.enums import SourceFilter
from museflow.domain.enums import TrackSource
from museflow.domain.exceptions import UserNotFound
from museflow.infrastructure.entrypoints.cli.commands.tracks import app
from museflow.infrastructure.entrypoints.cli.dependencies import get_unit_of_work
from museflow.infrastructure.entrypoints.cli.options import EMAIL_OPTION


@dataclass(frozen=True, kw_only=True)
class TracksDeleteResult:
    no_tracks: bool = False
    deleted_count: int = 0


@app.command("delete", help="Delete tracks matching the given filters.")
def delete(
    email: str = EMAIL_OPTION,
    artist: str | None = typer.Option(None, "--artist", help="Filter by primary artist name (case-insensitive)"),
    name: str | None = typer.Option(None, "--name", help="Filter by track name (case-insensitive)"),
    source: SourceFilter = typer.Option(SourceFilter.ALL, "--source", help="Filter by track source"),
    provider: MusicProvider | None = typer.Option(
        None, "--provider", help="Filter by music provider: unlink it, delete tracks left with none"
    ),
    purge: bool = typer.Option(False, "--purge", help="Delete all tracks, or only those matching --source/--provider"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
) -> None:
    if not purge and not artist and not name:
        raise typer.BadParameter("Provide at least --artist or --name, or use --purge to delete all tracks.")
    if purge and (artist or name):
        raise typer.BadParameter("--purge deletes all tracks: it can't be combined with --artist or --name.")

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

    typer.secho(f"Deleted {result.deleted_count} track(s) of {email}.", fg=typer.colors.GREEN)


async def delete_logic(
    email: EmailStr,
    artist: str | None,
    name: str | None,
    source: TrackSource | None,
    provider: MusicProvider | None,
    purge: bool = False,
    yes: bool = False,
) -> TracksDeleteResult:
    uow = get_unit_of_work()

    async with uow:
        user = await uow.users.get_by_email(email)

    if not user:
        raise UserNotFound()

    use_case = TracksDeleteUseCase(user_id=user.id, provider=provider, uow=uow)
    tracks = await use_case.find(artist=artist, name=name, source=source)

    count = len(tracks)
    if count == 0:
        return TracksDeleteResult(no_tracks=True)

    if artist and not name:
        for track in sorted(tracks, key=lambda t: t.name):
            typer.echo(f"  {track.name}")

    # The confirmation waits for the user: keep it out of any block.
    if not yes:
        typer.confirm(f"About to delete {count} track(s) of {email}. Continue?", abort=True)

    if purge and source is None:
        deleted = await use_case.delete_all()
    else:
        deleted = await use_case.delete(track_ids=[track.id for track in tracks])
    return TracksDeleteResult(deleted_count=deleted)
