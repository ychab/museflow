import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import EmailStr
from pydantic import TypeAdapter

import typer
import yaml

from museflow.application.inputs.rate import RateEntryInput
from museflow.domain.exceptions import UserNotFound
from museflow.infrastructure.entrypoints.cli.commands.rate import app
from museflow.infrastructure.entrypoints.cli.dependencies import get_unit_of_work
from museflow.infrastructure.entrypoints.cli.parsers import parse_email


@dataclass(frozen=True, kw_only=True)
class RateImportResult:
    imported_count: int
    skipped_count: int
    not_found_count: int


@app.command("import", help="Import track ratings from a YAML file.")
def import_(
    email: str = typer.Option(..., help="User email address", parser=parse_email),
    input_path: Path = typer.Option(..., "--input", help="Path to the input YAML file"),
) -> None:
    try:
        with input_path.open("r", encoding="utf-8") as f:
            data: list[Any] = yaml.safe_load(f)
    except FileNotFoundError:
        typer.secho(f"Error: File not found: {input_path}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from None
    except yaml.YAMLError as e:
        typer.secho(f"Error: Invalid YAML file: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e

    try:
        result = asyncio.run(import_logic(email=email, data=data))
    except UserNotFound as e:
        raise typer.BadParameter(f"User not found with email: {email}") from e
    except Exception as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e

    typer.secho(
        f"Imported {result.imported_count} score(s) and {result.skipped_count} permanent skip(s) "
        f"({result.not_found_count} fingerprints not found in DB).",
        fg=typer.colors.GREEN,
    )


async def import_logic(email: EmailStr, data: list[Any]) -> RateImportResult:
    entries = TypeAdapter(list[RateEntryInput]).validate_python(data)

    # One block: the import is saved as a whole, or not at all.
    async with get_unit_of_work() as uow:
        user = await uow.users.get_by_email(email)
        if user is None:
            raise UserNotFound()

        all_tracks = await uow.tracks.get_list(user_id=user.id)
        fingerprint_to_id = {t.fingerprint: t.id for t in all_tracks}

        imported_count = 0
        skipped_count = 0
        not_found_count = 0
        for entry in entries:
            if entry.fingerprint not in fingerprint_to_id:
                not_found_count += 1
                continue
            track_id = fingerprint_to_id[entry.fingerprint]
            if entry.score_skipped:
                await uow.tracks.skip(user_id=user.id, track_id=track_id)
                skipped_count += 1
            elif entry.score is not None:
                await uow.tracks.rate(user_id=user.id, track_id=track_id, score=entry.score)
                imported_count += 1

    return RateImportResult(
        imported_count=imported_count, skipped_count=skipped_count, not_found_count=not_found_count
    )
