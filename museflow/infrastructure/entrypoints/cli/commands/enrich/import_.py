import asyncio
import dataclasses
from contextlib import AsyncExitStack
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import EmailStr
from pydantic import TypeAdapter

import typer
import yaml

from museflow.application.inputs.enrich import EnrichEntryInput
from museflow.domain.enums import EnrichField
from museflow.domain.exceptions import UserNotFound
from museflow.infrastructure.entrypoints.cli.commands.enrich import app
from museflow.infrastructure.entrypoints.cli.dependencies import get_db
from museflow.infrastructure.entrypoints.cli.dependencies import get_track_repository
from museflow.infrastructure.entrypoints.cli.dependencies import get_user_repository
from museflow.infrastructure.entrypoints.cli.parsers import parse_email


@dataclass(frozen=True, kw_only=True)
class EnrichImportResult:
    imported_count: int
    not_found_count: int


@app.command("import", help="Import track enrichment data (genres and moods) from a YAML file.")
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
        f"Imported enrichment for {result.imported_count} track(s) "
        f"({result.not_found_count} fingerprints not found in DB).",
        fg=typer.colors.GREEN,
    )


async def import_logic(email: EmailStr, data: list[Any]) -> EnrichImportResult:
    async with AsyncExitStack() as stack:
        session = await stack.enter_async_context(get_db())

        user_repository = get_user_repository(session)
        track_repository = get_track_repository(session)

        user = await user_repository.get_by_email(email)
        if user is None:
            raise UserNotFound()

        entries = TypeAdapter(list[EnrichEntryInput]).validate_python(data)

        all_tracks = await track_repository.get_list(user_id=user.id)
        fingerprint_to_track = {t.fingerprint: t for t in all_tracks}

        updated_tracks = []
        not_found_count = 0
        for entry in entries:
            if entry.fingerprint not in fingerprint_to_track:
                not_found_count += 1
                continue
            track = fingerprint_to_track[entry.fingerprint]
            updated_tracks.append(
                dataclasses.replace(track, genres=entry.genres, moods=entry.moods, locale=entry.locale)
            )

        if updated_tracks:
            await track_repository.bulk_update(updated_tracks, fields=frozenset(EnrichField))

        return EnrichImportResult(imported_count=len(updated_tracks), not_found_count=not_found_count)
