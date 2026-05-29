import asyncio
from contextlib import AsyncExitStack

from pydantic import EmailStr

import typer
from rich.console import Console
from rich.table import Table

from museflow.application.use_cases.list_blacklist import list_blacklist
from museflow.domain.exceptions import UserNotFound
from museflow.domain.value_objects.blacklist import UserBlacklist
from museflow.infrastructure.entrypoints.cli.commands.blacklist import app
from museflow.infrastructure.entrypoints.cli.dependencies import get_blacklist_repository
from museflow.infrastructure.entrypoints.cli.dependencies import get_db
from museflow.infrastructure.entrypoints.cli.dependencies import get_user_repository
from museflow.infrastructure.entrypoints.cli.parsers import parse_email

console = Console()


@app.command("list", help="List all your blacklisted artists and tracks.")
def list_(
    email: str = typer.Option(..., help="User email address", parser=parse_email),
) -> None:
    try:
        blacklist = asyncio.run(list_logic(email=email))
    except UserNotFound as e:
        raise typer.BadParameter(f"User not found with email: {email}") from e
    except Exception as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e

    if blacklist.is_empty:
        typer.secho("Your blacklist is empty.", fg=typer.colors.YELLOW)
        return

    table = Table(title="Your Blacklist")
    table.add_column("ID", style="dim")
    table.add_column("Type")
    table.add_column("Artist Name")
    table.add_column("Track Name")

    for artist in blacklist.artists:
        table.add_row(str(artist.id), "artist", artist.artist_name, "")

    for track in blacklist.tracks:
        table.add_row(str(track.id), "track", track.artist_name, track.name)

    console.print(table)


async def list_logic(email: EmailStr) -> UserBlacklist:
    async with AsyncExitStack() as stack:
        session = await stack.enter_async_context(get_db())

        user = await get_user_repository(session).get_by_email(email)
        if not user:
            raise UserNotFound()

        return await list_blacklist(user_id=user.id, blacklist_repository=get_blacklist_repository(session))
