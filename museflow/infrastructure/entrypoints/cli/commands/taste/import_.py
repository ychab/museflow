import asyncio
from pathlib import Path
from typing import Any

from pydantic import EmailStr
from pydantic import TypeAdapter

import typer

from museflow.application.use_cases.taste_profile_import import import_taste_profiles
from museflow.domain.entities.taste import TasteProfile
from museflow.domain.exceptions import UserNotFoundError
from museflow.infrastructure.entrypoints.cli.commands.taste import app
from museflow.infrastructure.entrypoints.cli.dependencies import get_unit_of_work
from museflow.infrastructure.entrypoints.cli.options import EMAIL_OPTION
from museflow.infrastructure.entrypoints.cli.utils.files import read_yaml


@app.command("import", help="Import taste profiles from a YAML file.")
def taste_import_command(
    email: str = EMAIL_OPTION,
    input_path: Path = typer.Option(..., "--input", help="Path to the input YAML file"),
) -> None:
    data = read_yaml(input_path)

    try:
        taste_profiles = asyncio.run(taste_import_logic(email=email, data=data))
    except UserNotFoundError as e:
        raise typer.BadParameter(f"User not found with email: {email}") from e
    except Exception as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e

    names = ", ".join(f"'{profile.name}'" for profile in taste_profiles)
    typer.secho(f"Imported {len(taste_profiles)} taste profile(s): {names}", fg=typer.colors.GREEN)


async def taste_import_logic(email: EmailStr, data: list[dict[str, Any]] | dict[str, Any]) -> list[TasteProfile]:
    uow = get_unit_of_work()
    async with uow:
        user = await uow.users.get_by_email(email)

    if user is None:
        raise UserNotFoundError()

    # A file exported before the multi-profile export holds a single profile, not a list.
    entries = data if isinstance(data, list) else [data]
    taste_profiles = TypeAdapter(list[TasteProfile]).validate_python(entries)
    return await import_taste_profiles(user_id=user.id, taste_profiles=taste_profiles, uow=uow)
