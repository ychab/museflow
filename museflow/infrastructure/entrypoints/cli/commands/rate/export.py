import asyncio
from pathlib import Path
from typing import Any

from pydantic import EmailStr

import typer
import yaml

from museflow.domain.const import DISCOVERY_TRACK_SCORE_MIN
from museflow.domain.exceptions import UserNotFound
from museflow.infrastructure.entrypoints.cli.commands.rate import app
from museflow.infrastructure.entrypoints.cli.dependencies import get_unit_of_work
from museflow.infrastructure.entrypoints.cli.parsers import parse_email


@app.command("export", help="Export track ratings to a YAML file.")
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

    rated_count = sum(1 for entry in data if entry.get("score") is not None)
    skipped_count = sum(1 for entry in data if entry.get("score_skipped"))
    typer.secho(
        f"Exported {rated_count} rated track(s) and {skipped_count} permanently skipped track(s) to {output}",
        fg=typer.colors.GREEN,
    )


async def export_logic(email: EmailStr) -> list[dict[str, Any]]:
    async with get_unit_of_work() as uow:
        user = await uow.users.get_by_email(email)
        if user is None:
            raise UserNotFound()

        rated = await uow.tracks.get_list(user_id=user.id, min_score=DISCOVERY_TRACK_SCORE_MIN)
        skipped = await uow.tracks.get_list(user_id=user.id, score_skipped_only=True)

    result: list[dict[str, Any]] = [{"fingerprint": t.fingerprint, "score": t.score} for t in rated]
    result += [{"fingerprint": t.fingerprint, "score_skipped": True} for t in skipped]
    return result
