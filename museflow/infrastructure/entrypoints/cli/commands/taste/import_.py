import asyncio
import uuid
from contextlib import AsyncExitStack
from dataclasses import replace
from pathlib import Path
from typing import Any

from pydantic import EmailStr
from pydantic import TypeAdapter

import typer
import yaml

from museflow.domain.entities.taste import TasteProfile
from museflow.domain.exceptions import UserNotFound
from museflow.infrastructure.entrypoints.cli.commands.taste import app
from museflow.infrastructure.entrypoints.cli.dependencies import get_db
from museflow.infrastructure.entrypoints.cli.dependencies import get_taste_profile_repository
from museflow.infrastructure.entrypoints.cli.dependencies import get_user_repository
from museflow.infrastructure.entrypoints.cli.parsers import parse_email


@app.command("import", help="Import a taste profile from a YAML file.")
def import_(
    email: str = typer.Option(..., help="User email address", parser=parse_email),
    input_path: Path = typer.Option(..., "--input", help="Path to the input YAML file"),
) -> None:
    try:
        with input_path.open("r", encoding="utf-8") as f:
            data: dict[str, Any] = yaml.safe_load(f)
    except FileNotFoundError:
        typer.secho(f"Error: File not found: {input_path}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from None
    except yaml.YAMLError as e:
        typer.secho(f"Error: Invalid YAML file: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e

    try:
        taste_profile = asyncio.run(import_logic(email=email, data=data))
    except UserNotFound as e:
        raise typer.BadParameter(f"User not found with email: {email}") from e
    except Exception as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e

    typer.secho(f"Taste profile '{taste_profile.name}' imported successfully.", fg=typer.colors.GREEN)


async def import_logic(email: EmailStr, data: dict[str, Any]) -> TasteProfile:
    async with AsyncExitStack() as stack:
        session = await stack.enter_async_context(get_db())

        user_repository = get_user_repository(session)
        taste_profile_repository = get_taste_profile_repository(session)

        user = await user_repository.get_by_email(email)
        if user is None:
            raise UserNotFound()

        profile = TypeAdapter(TasteProfile).validate_python(data)
        profile = replace(profile, id=uuid.uuid4(), user_id=user.id)

        return await taste_profile_repository.upsert(profile)
