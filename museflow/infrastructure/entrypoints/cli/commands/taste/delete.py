import asyncio

from pydantic import EmailStr

import typer

from museflow.application.use_cases.taste_profile_delete import delete_taste_profile
from museflow.domain.exceptions import TasteProfileNotFoundException
from museflow.domain.exceptions import UserNotFound
from museflow.infrastructure.entrypoints.cli.commands.taste import app
from museflow.infrastructure.entrypoints.cli.dependencies import get_unit_of_work
from museflow.infrastructure.entrypoints.cli.parsers import parse_email


@app.command("delete", help="Delete a taste profile. Playlists built from it are kept.")
def delete(
    email: str = typer.Option(..., help="User email address", parser=parse_email),
    name: str = typer.Option(..., help="Profile name (unique per user)"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
) -> None:
    if not yes:
        typer.confirm(
            f"About to delete the taste profile '{name}'. Rebuilding it takes a full LLM build: "
            "export it first with `taste export`. Continue?",
            abort=True,
        )

    try:
        asyncio.run(delete_logic(email=email, name=name))
    except UserNotFound as e:
        raise typer.BadParameter(f"User not found with email: {email}") from e
    except TasteProfileNotFoundException as e:
        raise typer.BadParameter(f"Taste profile not found with name: {name}") from e
    except Exception as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e

    typer.secho(f"Taste profile '{name}' deleted.", fg=typer.colors.GREEN)


async def delete_logic(email: EmailStr, name: str) -> None:
    uow = get_unit_of_work()

    async with uow:
        user = await uow.users.get_by_email(email)
        if user is None:
            raise UserNotFound()

    await delete_taste_profile(user_id=user.id, name=name, uow=uow)
