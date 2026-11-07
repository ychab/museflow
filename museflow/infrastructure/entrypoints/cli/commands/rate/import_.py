import asyncio
from pathlib import Path
from typing import Any

from pydantic import EmailStr
from pydantic import TypeAdapter

import typer

from museflow.application.inputs.rate import RatingEntryInput
from museflow.application.use_cases.ratings_import import ImportRatingsResult
from museflow.application.use_cases.ratings_import import import_ratings
from museflow.domain.exceptions import UserNotFound
from museflow.infrastructure.entrypoints.cli.commands.rate import app
from museflow.infrastructure.entrypoints.cli.dependencies import get_unit_of_work
from museflow.infrastructure.entrypoints.cli.options import EMAIL_OPTION
from museflow.infrastructure.entrypoints.cli.utils.files import read_yaml


@app.command("import", help="Import track ratings from a YAML file.")
def rate_import_command(
    email: str = EMAIL_OPTION,
    input_path: Path = typer.Option(..., "--input", help="Path to the input YAML file"),
) -> None:
    data = read_yaml(input_path)

    try:
        result = asyncio.run(rate_import_logic(email=email, data=data))
    except UserNotFound as e:
        raise typer.BadParameter(f"User not found with email: {email}") from e
    except Exception as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e

    typer.secho(
        f"Imported {result.imported_count} score(s) and {result.skipped_count} permanent skip(s) "
        f"({result.not_found_count} fingerprints not found in DB).",
        fg=typer.colors.GREEN,
    )


async def rate_import_logic(email: EmailStr, data: list[Any]) -> ImportRatingsResult:
    entries = TypeAdapter(list[RatingEntryInput]).validate_python(data)

    uow = get_unit_of_work()
    async with uow:
        user = await uow.users.get_by_email(email)

    if user is None:
        raise UserNotFound()

    return await import_ratings(user_id=user.id, entries=entries, uow=uow)
