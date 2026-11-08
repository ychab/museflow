import asyncio
from pathlib import Path

from pydantic import EmailStr
from pydantic import TypeAdapter

import typer

from museflow.application.use_cases.taste_profile_list import get_taste_profiles
from museflow.application.use_cases.taste_profile_view import get_taste_profile
from museflow.domain.entities.taste import TasteProfile
from museflow.domain.exceptions import TasteProfileNotFoundError
from museflow.domain.exceptions import UserNotFoundError
from museflow.infrastructure.entrypoints.cli.commands.taste import app
from museflow.infrastructure.entrypoints.cli.dependencies import get_unit_of_work
from museflow.infrastructure.entrypoints.cli.options import EMAIL_OPTION
from museflow.infrastructure.entrypoints.cli.utils.files import write_yaml


@app.command("export", help="Export taste profiles to a YAML file.")
def taste_export_command(
    email: str = EMAIL_OPTION,
    name: str | None = typer.Option(None, help="Profile name (unique per user); every profile when omitted"),
    output: Path = typer.Option(..., help="Path to the output YAML file"),
) -> None:
    try:
        taste_profiles = asyncio.run(taste_export_logic(email=email, name=name))
    except UserNotFoundError as e:
        raise typer.BadParameter(f"User not found with email: {email}") from e
    except TasteProfileNotFoundError as e:
        raise typer.BadParameter(f"Taste profile not found with name: {name}") from e
    except Exception as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e

    write_yaml(output, TypeAdapter(list[TasteProfile]).dump_python(taste_profiles, mode="json"))

    names = ", ".join(f"'{profile.name}'" for profile in taste_profiles)
    typer.secho(f"Exported {len(taste_profiles)} taste profile(s) to {output}: {names}", fg=typer.colors.GREEN)


async def taste_export_logic(email: EmailStr, name: str | None = None) -> list[TasteProfile]:
    uow = get_unit_of_work()
    async with uow:
        user = await uow.users.get_by_email(email)

    if user is None:
        raise UserNotFoundError()

    if name is None:
        return await get_taste_profiles(user_id=user.id, uow=uow)

    # Exporting one profile reads it exactly as viewing it does.
    return [await get_taste_profile(user_id=user.id, name=name, uow=uow)]
