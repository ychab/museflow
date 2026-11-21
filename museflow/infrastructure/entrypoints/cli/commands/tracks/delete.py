from dataclasses import dataclass
from typing import Annotated

from pydantic import EmailStr

import typer

from museflow.application.use_cases.track_delete import DeleteTracksUseCase
from museflow.application.use_cases.user_get import get_user
from museflow.domain.enums import MusicProvider
from museflow.domain.enums import SourceFilter
from museflow.domain.enums import TrackSource
from museflow.domain.exceptions import UserNotFoundError
from museflow.infrastructure.entrypoints.cli.commands.tracks import app
from museflow.infrastructure.entrypoints.cli.dependencies import get_wiring
from museflow.infrastructure.entrypoints.cli.dependencies import run_logic
from museflow.infrastructure.entrypoints.cli.options import EmailOption


@dataclass(frozen=True, kw_only=True)
class TracksDeleteResult:
    no_tracks: bool = False
    deleted_count: int = 0


@app.command("delete", help="Delete tracks matching the given filters.")
def tracks_delete_command(
    email: EmailOption,
    artist: Annotated[
        str | None, typer.Option("--artist", help="Filter by primary artist name (case-insensitive)")
    ] = None,
    name: Annotated[str | None, typer.Option("--name", help="Filter by track name (case-insensitive)")] = None,
    source: Annotated[SourceFilter, typer.Option("--source", help="Filter by track source")] = SourceFilter.ALL,
    provider: Annotated[
        MusicProvider | None,
        typer.Option("--provider", help="Filter by music provider: unlink it, delete tracks left with none"),
    ] = None,
    purge: Annotated[
        bool, typer.Option("--purge", help="Delete all tracks, or only those matching --source/--provider")
    ] = False,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation prompt")] = False,
) -> None:
    if not purge and not artist and not name:
        raise typer.BadParameter("Provide at least --artist or --name, or use --purge to delete all tracks.")
    if purge and (artist or name):
        raise typer.BadParameter("--purge deletes all tracks: it can't be combined with --artist or --name.")

    try:
        result = run_logic(
            tracks_delete_logic(
                email=email,
                artist=artist,
                name=name,
                source=source.to_track_source(),
                provider=provider,
                purge=purge,
                yes=yes,
            )
        )
    except UserNotFoundError as e:
        raise typer.BadParameter(f"User not found with email: {email}") from e
    except Exception as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e

    if result.no_tracks:
        typer.secho("No tracks found matching the filters.", fg=typer.colors.YELLOW)
        return

    typer.secho(f"Deleted {result.deleted_count} track(s) of {email}.", fg=typer.colors.GREEN)


async def tracks_delete_logic(
    email: EmailStr,
    artist: str | None,
    name: str | None,
    source: TrackSource | None,
    provider: MusicProvider | None,
    purge: bool = False,
    yes: bool = False,
) -> TracksDeleteResult:
    uow = get_wiring().build_unit_of_work()

    user = await get_user(email=email, uow=uow)

    use_case = DeleteTracksUseCase(user_id=user.id, provider=provider, uow=uow)
    tracks = await use_case.find(artist=artist, name=name, source=source)

    count = len(tracks)
    if count == 0:
        return TracksDeleteResult(no_tracks=True)

    if artist and not name:
        for track in sorted(tracks, key=lambda t: t.name):
            typer.echo(f"  {track.name}")

    # The confirmation waits for the user: keep it out of any block.
    if not yes:
        typer.confirm(
            typer.style(f"About to delete {count} track(s) of {email}. Continue?", fg=typer.colors.YELLOW), abort=True
        )

    if purge and source is None:
        deleted = await use_case.purge()
    else:
        deleted = await use_case.delete(track_ids=[track.id for track in tracks])

    return TracksDeleteResult(deleted_count=deleted)
