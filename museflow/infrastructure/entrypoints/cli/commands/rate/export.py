import asyncio
from pathlib import Path
from typing import Any

from pydantic import EmailStr

import typer

from museflow.application.use_cases.ratings_export import export_ratings
from museflow.domain.entities.track import Track
from museflow.domain.exceptions import UserNotFoundError
from museflow.infrastructure.entrypoints.cli.commands.rate import app
from museflow.infrastructure.entrypoints.cli.dependencies import get_unit_of_work
from museflow.infrastructure.entrypoints.cli.options import EMAIL_OPTION
from museflow.infrastructure.entrypoints.cli.utils.files import write_yaml


def _dump_track(track: Track) -> dict[str, Any]:
    # What recreates the track on import when the library lacks it (e.g. a discovery never played, after a reset)
    return {
        "fingerprint": track.fingerprint,
        "name": track.name,
        "artists": track.artists,
        "album_name": track.album_name,
        "source": int(track.source),
        "provider_links": [
            {"provider": link.provider.value, "provider_id": link.provider_id} for link in track.provider_links
        ],
    }


@app.command("export", help="Export track ratings to a YAML file.")
def rate_export_command(
    email: str = EMAIL_OPTION,
    output: Path = typer.Option(..., help="Path to the output YAML file"),
) -> None:
    try:
        data = asyncio.run(rate_export_logic(email=email))
    except UserNotFoundError as e:
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


async def rate_export_logic(email: EmailStr) -> list[dict[str, Any]]:
    uow = get_unit_of_work()
    async with uow:
        user = await uow.users.get_by_email(email)

    if user is None:
        raise UserNotFoundError()

    ratings = await export_ratings(user_id=user.id, uow=uow)

    result: list[dict[str, Any]] = [{**_dump_track(t), "score": t.score} for t in ratings.rated]
    result += [{**_dump_track(t), "score_skipped": True} for t in ratings.skipped]
    return result
