import asyncio
from pathlib import Path

from pydantic import EmailStr

import typer

from museflow.application.inputs.llm import LLMUsageEntryInput
from museflow.application.use_cases.llm_usage_export import export_llm_usage
from museflow.domain.exceptions import UserNotFoundError
from museflow.infrastructure.entrypoints.cli.commands.llm import app
from museflow.infrastructure.entrypoints.cli.dependencies import get_unit_of_work
from museflow.infrastructure.entrypoints.cli.options import EMAIL_OPTION
from museflow.infrastructure.entrypoints.cli.utils.files import write_yaml


@app.command("export", help="Export the LLM usage history to a YAML file.")
def llm_export_command(
    email: str = EMAIL_OPTION,
    output: Path = typer.Option(..., help="Path to the output YAML file"),
) -> None:
    try:
        entries = asyncio.run(llm_export_logic(email=email))
    except UserNotFoundError as e:
        raise typer.BadParameter(f"User not found with email: {email}") from e
    except Exception as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e

    write_yaml(output, [entry.model_dump(mode="json") for entry in entries])

    typer.secho(f"Exported {len(entries)} LLM usage row(s) to {output}", fg=typer.colors.GREEN)


async def llm_export_logic(email: EmailStr) -> list[LLMUsageEntryInput]:
    uow = get_unit_of_work()
    async with uow:
        user = await uow.users.get_by_email(email)

    if user is None:
        raise UserNotFoundError()

    return await export_llm_usage(user_id=user.id, uow=uow)
