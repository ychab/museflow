import asyncio

from pydantic import EmailStr

import typer
from rich.table import Table

from museflow.application.use_cases.taste_profile_list import list_taste_profiles
from museflow.domain.entities.taste import TasteProfile
from museflow.domain.exceptions import UserNotFound
from museflow.infrastructure.entrypoints.cli.commands.taste import app
from museflow.infrastructure.entrypoints.cli.commands.taste import console
from museflow.infrastructure.entrypoints.cli.dependencies import get_unit_of_work
from museflow.infrastructure.entrypoints.cli.parsers import parse_email


@app.command("list", help="List all taste profiles for a user.")
def list_(
    email: str = typer.Option(..., help="User email address", parser=parse_email),
) -> None:
    try:
        profiles = asyncio.run(list_logic(email=email))
    except UserNotFound as e:
        raise typer.BadParameter(f"User not found with email: {email}") from e
    except Exception as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e

    if not profiles:
        typer.secho("No taste profiles found.", fg=typer.colors.YELLOW)
        return

    table = Table(title="Taste Profiles")
    table.add_column("ID", style="dim")
    table.add_column("Name")
    table.add_column("Profiler")
    table.add_column("Status")
    table.add_column("Tracks")
    table.add_column("Updated At")

    for profile in profiles:
        table.add_row(
            str(profile.id),
            profile.name,
            profile.profiler.value,
            profile.status.value,
            str(profile.tracks_count),
            profile.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
        )

    console.print(table)


async def list_logic(email: EmailStr) -> list[TasteProfile]:
    uow = get_unit_of_work()

    async with uow:
        user = await uow.users.get_by_email(email)

    if not user:
        raise UserNotFound()

    return await list_taste_profiles(user_id=user.id, uow=uow)
