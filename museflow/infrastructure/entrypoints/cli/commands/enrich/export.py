import asyncio
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any

from pydantic import EmailStr

import typer
import yaml

from museflow.domain.exceptions import UserNotFound
from museflow.infrastructure.entrypoints.cli.commands.enrich import app
from museflow.infrastructure.entrypoints.cli.dependencies import get_db
from museflow.infrastructure.entrypoints.cli.dependencies import get_track_repository
from museflow.infrastructure.entrypoints.cli.dependencies import get_user_repository
from museflow.infrastructure.entrypoints.cli.parsers import parse_email


@app.command("export", help="Export track enrichment data (genres and moods) to a YAML file.")
def export(
    email: str = typer.Option(..., help="User email address", parser=parse_email),
    output: Path = typer.Option(..., help="Path to the output YAML file"),
) -> None:
    try:
        data = asyncio.run(export_logic(email=email))
    except UserNotFound as e:
        raise typer.BadParameter(f"User not found with email: {email}") from e
    except Exception as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e

    with output.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    typer.secho(
        f"Exported enrichment for {len(data)} track(s) to {output}",
        fg=typer.colors.GREEN,
    )


async def export_logic(email: EmailStr) -> list[dict[str, Any]]:
    async with AsyncExitStack() as stack:
        session = await stack.enter_async_context(get_db())

        user_repository = get_user_repository(session)
        track_repository = get_track_repository(session)

        user = await user_repository.get_by_email(email)
        if user is None:
            raise UserNotFound()

        tracks = await track_repository.get_list(user_id=user.id)
        enriched = [t for t in tracks if t.genres]
        return [
            {"fingerprint": t.fingerprint, "genres": [g.value for g in t.genres], "moods": [m.value for m in t.moods]}
            for t in enriched
        ]
