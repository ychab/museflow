import asyncio
from pathlib import Path

from pydantic import EmailStr
from pydantic import TypeAdapter

import typer

from museflow.application.use_cases.taste_profile_view import view_taste_profile
from museflow.domain.entities.taste import TasteProfile
from museflow.domain.exceptions import TasteProfileNotFoundException
from museflow.domain.exceptions import UserNotFound
from museflow.infrastructure.entrypoints.cli.commands.taste import app
from museflow.infrastructure.entrypoints.cli.dependencies import get_unit_of_work
from museflow.infrastructure.entrypoints.cli.options import EMAIL_OPTION
from museflow.infrastructure.entrypoints.cli.utils.files import write_yaml


@app.command("export", help="Export a taste profile to a YAML file.")
def export(
    email: str = EMAIL_OPTION,
    name: str = typer.Option(..., help="Profile name (unique per user)"),
    output: Path = typer.Option(..., help="Path to the output YAML file"),
) -> None:
    try:
        taste_profile = asyncio.run(export_logic(email=email, name=name))
    except UserNotFound as e:
        raise typer.BadParameter(f"User not found with email: {email}") from e
    except TasteProfileNotFoundException as e:
        raise typer.BadParameter(f"Taste profile not found with name: {name}") from e
    except Exception as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e

    write_yaml(output, TypeAdapter(TasteProfile).dump_python(taste_profile, mode="json"))

    typer.secho(f"Taste profile '{name}' exported to {output}", fg=typer.colors.GREEN)


async def export_logic(email: EmailStr, name: str) -> TasteProfile:
    uow = get_unit_of_work()
    async with uow:
        user = await uow.users.get_by_email(email)

    if user is None:
        raise UserNotFound()

    # Exporting reads the profile exactly as viewing it does.
    return await view_taste_profile(user_id=user.id, name=name, uow=uow)
