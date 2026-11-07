import asyncio
from pathlib import Path
from typing import Any

from pydantic import EmailStr

import typer

from museflow.application.use_cases.ratings_export import export_ratings
from museflow.domain.exceptions import UserNotFound
from museflow.infrastructure.entrypoints.cli.commands.rate import app
from museflow.infrastructure.entrypoints.cli.dependencies import get_unit_of_work
from museflow.infrastructure.entrypoints.cli.options import EMAIL_OPTION
from museflow.infrastructure.entrypoints.cli.utils.files import write_yaml


@app.command("export", help="Export track ratings to a YAML file.")
def export(
    email: str = EMAIL_OPTION,
    output: Path = typer.Option(..., help="Path to the output YAML file"),
) -> None:
    try:
        data = asyncio.run(export_logic(email=email))
    except UserNotFound as e:
        raise typer.BadParameter(f"User not found with email: {email}") from e
    except Exception as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e

    write_yaml(output, data)

    rated_count = sum(1 for entry in data if entry.get("score") is not None)
    skipped_count = sum(1 for entry in data if entry.get("score_skipped"))
    typer.secho(
        f"Exported {rated_count} rated track(s) and {skipped_count} permanently skipped track(s) to {output}",
        fg=typer.colors.GREEN,
    )


async def export_logic(email: EmailStr) -> list[dict[str, Any]]:
    uow = get_unit_of_work()
    async with uow:
        user = await uow.users.get_by_email(email)

    if user is None:
        raise UserNotFound()

    ratings = await export_ratings(user_id=user.id, uow=uow)

    result: list[dict[str, Any]] = [{"fingerprint": t.fingerprint, "score": t.score} for t in ratings.rated]
    result += [{"fingerprint": t.fingerprint, "score_skipped": True} for t in ratings.skipped]
    return result
