import asyncio
from pathlib import Path
from typing import Any

from pydantic import EmailStr
from pydantic import TypeAdapter

import typer

from museflow.application.inputs.llm import LLMUsageEntryInput
from museflow.application.use_cases.llm_usage_import import ImportLLMUsageResult
from museflow.application.use_cases.llm_usage_import import import_llm_usage
from museflow.domain.exceptions import UserNotFoundError
from museflow.infrastructure.entrypoints.cli.commands.llm import app
from museflow.infrastructure.entrypoints.cli.dependencies import get_unit_of_work
from museflow.infrastructure.entrypoints.cli.options import EMAIL_OPTION
from museflow.infrastructure.entrypoints.cli.utils.files import read_yaml


@app.command(
    "import",
    help="Import an LLM usage history from a YAML file; rows already there are skipped. Import the profiles first.",
)
def llm_import_command(
    email: str = EMAIL_OPTION,
    input_path: Path = typer.Option(..., "--input", help="Path to the input YAML file"),
) -> None:
    data = read_yaml(input_path)

    try:
        result = asyncio.run(llm_import_logic(email=email, data=data))
    except UserNotFoundError as e:
        raise typer.BadParameter(f"User not found with email: {email}") from e
    except Exception as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e

    typer.secho(
        f"Imported {result.imported_count} LLM usage row(s) ({result.skipped_count} already there).",
        fg=typer.colors.GREEN,
    )


async def llm_import_logic(email: EmailStr, data: Any) -> ImportLLMUsageResult:
    entries = TypeAdapter(list[LLMUsageEntryInput]).validate_python(data)

    uow = get_unit_of_work()
    async with uow:
        user = await uow.users.get_by_email(email)

    if user is None:
        raise UserNotFoundError()

    return await import_llm_usage(user_id=user.id, entries=entries, uow=uow)
