from pathlib import Path
from typing import Annotated
from typing import Any

from pydantic import EmailStr

import typer

from museflow.application.use_cases.track_enrichment_export import export_enrichment
from museflow.application.use_cases.user_get import get_user
from museflow.domain.exceptions import UserNotFoundError
from museflow.infrastructure.entrypoints.cli.commands.enrich import app
from museflow.infrastructure.entrypoints.cli.dependencies import get_wiring
from museflow.infrastructure.entrypoints.cli.dependencies import run_logic
from museflow.infrastructure.entrypoints.cli.options import EmailOption
from museflow.infrastructure.entrypoints.cli.utils.files import write_yaml


@app.command("export", help="Export track enrichment data (genres and moods) to a YAML file.")
def enrich_export_command(
    email: EmailOption,
    output: Annotated[Path, typer.Option(help="Path to the output YAML file")],
) -> None:
    try:
        data = run_logic(enrich_export_logic(email=email))
    except UserNotFoundError as e:
        raise typer.BadParameter(f"User not found with email: {email}") from e
    except Exception as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e

    write_yaml(output, data)

    typer.secho(
        f"Exported enrichment for {len(data)} track(s) to {output}",
        fg=typer.colors.GREEN,
    )


async def enrich_export_logic(email: EmailStr) -> list[dict[str, Any]]:
    uow = get_wiring().build_unit_of_work()
    user = await get_user(email=email, uow=uow)

    tracks = await export_enrichment(user_id=user.id, uow=uow)

    return [
        {
            "fingerprint": t.fingerprint,
            "genres": [g.value for g in t.genres],
            "moods": [m.value for m in t.moods],
            "locales": t.locales,
        }
        for t in tracks
    ]
