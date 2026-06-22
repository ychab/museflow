import asyncio
import uuid
from contextlib import AsyncExitStack

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from museflow.application.use_cases.playlist_view import playlist_view
from museflow.domain.entities.playlist import Playlist
from museflow.domain.exceptions import PlaylistNotFoundError
from museflow.domain.exceptions import UserNotFound
from museflow.infrastructure.entrypoints.cli.commands.playlist import app
from museflow.infrastructure.entrypoints.cli.dependencies import get_db
from museflow.infrastructure.entrypoints.cli.dependencies import get_playlist_repository
from museflow.infrastructure.entrypoints.cli.dependencies import get_user_repository
from museflow.infrastructure.entrypoints.cli.parsers import parse_email

console = Console()


@app.command("view")
def view(
    playlist_id: uuid.UUID = typer.Argument(..., help="Playlist ID"),
    email: str = typer.Option(..., help="User email address", parser=parse_email),
) -> None:
    """View a playlist with its tracks and ratings."""
    try:
        playlist = asyncio.run(view_logic(email=email, playlist_id=playlist_id))
    except UserNotFound as e:
        raise typer.BadParameter(f"User not found with email: {email}") from e
    except PlaylistNotFoundError as e:
        typer.secho(f"Playlist {playlist_id} not found.", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e
    except Exception as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e

    console.print(
        Panel(
            playlist.reasoning or "—",
            title=f"{playlist.name} ({playlist.type.value})",
            border_style="blue",
        )
    )

    track_table = Table(title="Tracks")
    track_table.add_column("#", justify="right", style="dim")
    track_table.add_column("ID", style="dim")
    track_table.add_column("Artist(s)")
    track_table.add_column("Track")
    track_table.add_column("Score", justify="center")
    for i, track in enumerate(playlist.tracks, start=1):
        track_table.add_row(
            str(i),
            str(track.id),
            ", ".join(track.artists),
            track.name,
            str(track.score) if track.score is not None else "—",
        )
    console.print(track_table)


async def view_logic(email: str, playlist_id: uuid.UUID) -> Playlist:
    async with AsyncExitStack() as stack:
        session = await stack.enter_async_context(get_db())
        user_repository = get_user_repository(session)
        playlist_repository = get_playlist_repository(session)

        user = await user_repository.get_by_email(email)
        if not user:
            raise UserNotFound()

        return await playlist_view(
            user=user,
            playlist_id=playlist_id,
            playlist_repository=playlist_repository,
        )
