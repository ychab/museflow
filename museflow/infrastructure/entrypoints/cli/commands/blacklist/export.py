import asyncio
from pathlib import Path

from pydantic import EmailStr

import typer

from museflow.application.inputs.blacklist import BlacklistImportInput
from museflow.application.use_cases.blacklist_list import get_blacklist
from museflow.domain.exceptions import UserNotFoundError
from museflow.infrastructure.entrypoints.cli.commands.blacklist import app
from museflow.infrastructure.entrypoints.cli.dependencies import get_unit_of_work
from museflow.infrastructure.entrypoints.cli.options import EMAIL_OPTION
from museflow.infrastructure.entrypoints.cli.utils.files import write_yaml


@app.command("export", help="Export the blacklist to a YAML file.")
def blacklist_export_command(
    email: str = EMAIL_OPTION,
    output: Path = typer.Option(..., help="Path to the output YAML file"),
) -> None:
    try:
        blacklist_in = asyncio.run(blacklist_export_logic(email=email))
    except UserNotFoundError as e:
        raise typer.BadParameter(f"User not found with email: {email}") from e
    except Exception as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e

    write_yaml(output, blacklist_in.model_dump())

    typer.secho(
        f"Exported {len(blacklist_in.artists)} artist(s) and {len(blacklist_in.tracks)} track(s) to {output}",
        fg=typer.colors.GREEN,
    )


async def blacklist_export_logic(email: EmailStr) -> BlacklistImportInput:
    uow = get_unit_of_work()
    async with uow:
        user = await uow.users.get_by_email(email)

    if user is None:
        raise UserNotFoundError()

    # Exporting reads the blacklist exactly as listing it does.
    blacklist = await get_blacklist(user_id=user.id, uow=uow)

    # The file has the shape the import reads, so an export always imports back.
    return BlacklistImportInput.model_validate(blacklist)
