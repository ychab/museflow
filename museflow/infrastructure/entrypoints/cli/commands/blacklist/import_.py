import asyncio
from pathlib import Path
from typing import Any

from pydantic import EmailStr

import typer

from museflow.application.inputs.blacklist import BlacklistImportInput
from museflow.application.use_cases.blacklist_import import ImportBlacklistResult
from museflow.application.use_cases.blacklist_import import import_blacklist
from museflow.domain.exceptions import UserNotFoundError
from museflow.infrastructure.entrypoints.cli.commands.blacklist import app
from museflow.infrastructure.entrypoints.cli.dependencies import get_unit_of_work
from museflow.infrastructure.entrypoints.cli.options import EMAIL_OPTION
from museflow.infrastructure.entrypoints.cli.utils.files import read_yaml


@app.command("import", help="Import a blacklist from a YAML file; entries already blacklisted are skipped.")
def blacklist_import_command(
    email: str = EMAIL_OPTION,
    input_path: Path = typer.Option(..., "--input", help="Path to the input YAML file"),
) -> None:
    data = read_yaml(input_path)

    try:
        result = asyncio.run(blacklist_import_logic(email=email, data=data))
    except UserNotFoundError as e:
        raise typer.BadParameter(f"User not found with email: {email}") from e
    except Exception as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e

    typer.secho(
        f"Imported {result.imported_artists_count} artist(s) and {result.imported_tracks_count} track(s) "
        f"({result.skipped_count} already blacklisted).",
        fg=typer.colors.GREEN,
    )


async def blacklist_import_logic(email: EmailStr, data: Any) -> ImportBlacklistResult:
    blacklist_in = BlacklistImportInput.model_validate(data)

    uow = get_unit_of_work()
    async with uow:
        user = await uow.users.get_by_email(email)

    if user is None:
        raise UserNotFoundError()

    return await import_blacklist(user_id=user.id, blacklist_in=blacklist_in, uow=uow)
