import asyncio
from pathlib import Path
from typing import Any

from pydantic import EmailStr
from pydantic import TypeAdapter

import typer

from museflow.application.inputs.enrich import EnrichmentEntryInput
from museflow.application.use_cases.enrichment_import import ImportEnrichmentResult
from museflow.application.use_cases.enrichment_import import import_enrichment
from museflow.domain.exceptions import UserNotFound
from museflow.infrastructure.entrypoints.cli.commands.enrich import app
from museflow.infrastructure.entrypoints.cli.dependencies import get_unit_of_work
from museflow.infrastructure.entrypoints.cli.options import EMAIL_OPTION
from museflow.infrastructure.entrypoints.cli.utils.files import read_yaml


@app.command("import", help="Import track enrichment data (genres and moods) from a YAML file.")
def enrich_import_command(
    email: str = EMAIL_OPTION,
    input_path: Path = typer.Option(..., "--input", help="Path to the input YAML file"),
) -> None:
    data = read_yaml(input_path)

    try:
        result = asyncio.run(enrich_import_logic(email=email, data=data))
    except UserNotFound as e:
        raise typer.BadParameter(f"User not found with email: {email}") from e
    except Exception as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e

    typer.secho(
        f"Imported enrichment for {result.imported_count} track(s) "
        f"({result.not_found_count} fingerprints not found in DB).",
        fg=typer.colors.GREEN,
    )


async def enrich_import_logic(email: EmailStr, data: list[Any]) -> ImportEnrichmentResult:
    entries = TypeAdapter(list[EnrichmentEntryInput]).validate_python(data)

    uow = get_unit_of_work()
    async with uow:
        user = await uow.users.get_by_email(email)

    if user is None:
        raise UserNotFound()

    return await import_enrichment(user_id=user.id, entries=entries, uow=uow)
