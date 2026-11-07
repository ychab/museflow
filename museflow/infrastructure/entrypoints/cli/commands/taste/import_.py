import asyncio
from pathlib import Path
from typing import Any

from pydantic import EmailStr
from pydantic import TypeAdapter

import typer

from museflow.application.use_cases.taste_profile_import import import_taste_profile
from museflow.domain.entities.taste import TasteProfile
from museflow.domain.exceptions import UserNotFound
from museflow.infrastructure.entrypoints.cli.commands.taste import app
from museflow.infrastructure.entrypoints.cli.dependencies import get_unit_of_work
from museflow.infrastructure.entrypoints.cli.options import EMAIL_OPTION
from museflow.infrastructure.entrypoints.cli.utils.files import read_yaml


@app.command("import", help="Import a taste profile from a YAML file.")
def taste_import_command(
    email: str = EMAIL_OPTION,
    input_path: Path = typer.Option(..., "--input", help="Path to the input YAML file"),
) -> None:
    data = read_yaml(input_path)

    try:
        taste_profile = asyncio.run(taste_import_logic(email=email, data=data))
    except UserNotFound as e:
        raise typer.BadParameter(f"User not found with email: {email}") from e
    except Exception as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e

    typer.secho(f"Taste profile '{taste_profile.name}' imported successfully.", fg=typer.colors.GREEN)


async def taste_import_logic(email: EmailStr, data: dict[str, Any]) -> TasteProfile:
    uow = get_unit_of_work()
    async with uow:
        user = await uow.users.get_by_email(email)

    if user is None:
        raise UserNotFound()

    taste_profile = TypeAdapter(TasteProfile).validate_python(data)
    return await import_taste_profile(user_id=user.id, taste_profile=taste_profile, uow=uow)
