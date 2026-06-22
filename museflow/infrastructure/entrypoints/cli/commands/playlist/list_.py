import asyncio
from contextlib import AsyncExitStack

import typer
from rich.console import Console
from rich.table import Table

from museflow.application.use_cases.playlist_list import playlist_list
from museflow.domain.entities.playlist import Playlist
from museflow.domain.exceptions import UserNotFound
from museflow.infrastructure.entrypoints.cli.commands.playlist import app
from museflow.infrastructure.entrypoints.cli.dependencies import get_db
from museflow.infrastructure.entrypoints.cli.dependencies import get_playlist_repository
from museflow.infrastructure.entrypoints.cli.dependencies import get_user_repository
from museflow.infrastructure.entrypoints.cli.parsers import parse_email

console = Console()


@app.command("list")
def list_(
    email: str = typer.Option(..., help="User email address", parser=parse_email),
) -> None:
    """List all playlists for a user."""
    try:
        playlists = asyncio.run(list_logic(email=email))
    except UserNotFound as e:
        raise typer.BadParameter(f"User not found with email: {email}") from e
    except Exception as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e

    if not playlists:
        typer.secho("No playlists found. Run `muse playlist discover` first.", fg=typer.colors.YELLOW)
        return

    table = Table(title="Playlists")
    table.add_column("ID")
    table.add_column("Name")
    table.add_column("Type")
    table.add_column("Focus")
    table.add_column("Genre")
    table.add_column("Mood")
    table.add_column("Created")

    for playlist in playlists:
        table.add_row(
            str(playlist.id),
            playlist.name,
            playlist.type.value,
            playlist.focus.value if playlist.focus else "—",
            playlist.genre or "—",
            playlist.mood or "—",
            playlist.created_at.strftime("%Y-%m-%d %H:%M"),
        )

    console.print(table)


async def list_logic(email: str) -> list[Playlist]:
    async with AsyncExitStack() as stack:
        session = await stack.enter_async_context(get_db())
        user_repository = get_user_repository(session)
        playlist_repository = get_playlist_repository(session)

        user = await user_repository.get_by_email(email)
        if not user:
            raise UserNotFound()

        return await playlist_list(
            user=user,
            playlist_repository=playlist_repository,
        )
