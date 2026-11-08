import asyncio

import typer
from rich.console import Console
from rich.table import Table

from museflow.application.use_cases.playlist_list import get_playlists
from museflow.domain.entities.playlist import Playlist
from museflow.domain.exceptions import UserNotFoundError
from museflow.infrastructure.entrypoints.cli.commands.playlist import app
from museflow.infrastructure.entrypoints.cli.dependencies import get_unit_of_work
from museflow.infrastructure.entrypoints.cli.options import EMAIL_OPTION

console = Console()


@app.command("list")
def playlist_list_command(
    email: str = EMAIL_OPTION,
) -> None:
    """List all playlists for a user."""
    try:
        playlists = asyncio.run(playlist_list_logic(email=email))
    except UserNotFoundError as e:
        raise typer.BadParameter(f"User not found with email: {email}") from e
    except Exception as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e

    if not playlists:
        typer.secho("No playlists found. Run `museflow playlist discover` first.", fg=typer.colors.YELLOW)
        return

    table = Table(title="Playlists")
    table.add_column("ID")
    table.add_column("Name")
    table.add_column("Type")
    table.add_column("Prompt", max_width=40, overflow="ellipsis", no_wrap=True)
    table.add_column("Focus")
    table.add_column("Created")

    for playlist in playlists:
        table.add_row(
            str(playlist.id),
            playlist.name,
            playlist.type.value,
            playlist.prompt or "—",
            playlist.focus.value if playlist.focus else "—",
            playlist.created_at.strftime("%Y-%m-%d %H:%M"),
        )

    console.print(table)


async def playlist_list_logic(email: str) -> list[Playlist]:
    uow = get_unit_of_work()

    async with uow:
        user = await uow.users.get_by_email(email)

    if not user:
        raise UserNotFoundError()

    return await get_playlists(user=user, uow=uow)
