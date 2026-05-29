import asyncio
from contextlib import AsyncExitStack
from pathlib import Path

from pydantic import EmailStr
from pydantic import TypeAdapter

import typer
import yaml

from museflow.domain.entities.taste import TasteProfile
from museflow.domain.exceptions import TasteProfileNotFoundException
from museflow.domain.exceptions import UserNotFound
from museflow.infrastructure.entrypoints.cli.commands.taste import app
from museflow.infrastructure.entrypoints.cli.dependencies import get_db
from museflow.infrastructure.entrypoints.cli.dependencies import get_taste_profile_repository
from museflow.infrastructure.entrypoints.cli.dependencies import get_user_repository
from museflow.infrastructure.entrypoints.cli.parsers import parse_email


@app.command("export", help="Export a taste profile to a YAML file.")
def export(
    email: str = typer.Option(..., help="User email address", parser=parse_email),
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

    data = TypeAdapter(TasteProfile).dump_python(taste_profile, mode="json")
    with output.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    typer.secho(f"Taste profile '{name}' exported to {output}", fg=typer.colors.GREEN)


async def export_logic(email: EmailStr, name: str) -> TasteProfile:
    async with AsyncExitStack() as stack:
        session = await stack.enter_async_context(get_db())

        user_repository = get_user_repository(session)
        taste_profile_repository = get_taste_profile_repository(session)

        user = await user_repository.get_by_email(email)
        if user is None:
            raise UserNotFound()

        taste_profile = await taste_profile_repository.get(user_id=user.id, name=name)
        if not taste_profile:
            raise TasteProfileNotFoundException()

        return taste_profile
