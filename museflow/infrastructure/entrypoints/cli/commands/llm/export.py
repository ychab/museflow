from pathlib import Path
from typing import Annotated

from pydantic import EmailStr

import typer

from museflow.application.inputs.llm import LLMUsageEntryInput
from museflow.application.use_cases.llm_usage_export import export_llm_usage
from museflow.application.use_cases.user_get import get_user
from museflow.domain.exceptions import UserNotFoundError
from museflow.infrastructure.entrypoints.cli.commands.llm import app
from museflow.infrastructure.entrypoints.cli.dependencies import get_wiring
from museflow.infrastructure.entrypoints.cli.dependencies import run_logic
from museflow.infrastructure.entrypoints.cli.options import EmailOption
from museflow.infrastructure.entrypoints.cli.utils.files import write_yaml


@app.command("export", help="Export the LLM usage history to a YAML file.")
def llm_export_command(
    email: EmailOption,
    output: Annotated[Path, typer.Option(help="Path to the output YAML file")],
) -> None:
    try:
        entries = run_logic(llm_export_logic(email=email))
    except UserNotFoundError as e:
        raise typer.BadParameter(f"User not found with email: {email}") from e
    except Exception as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e

    write_yaml(output, [entry.model_dump(mode="json") for entry in entries])

    typer.secho(f"Exported {len(entries)} LLM usage row(s) to {output}", fg=typer.colors.GREEN)


async def llm_export_logic(email: EmailStr) -> list[LLMUsageEntryInput]:
    uow = get_wiring().build_unit_of_work()
    user = await get_user(email=email, uow=uow)

    return await export_llm_usage(user_id=user.id, uow=uow)
