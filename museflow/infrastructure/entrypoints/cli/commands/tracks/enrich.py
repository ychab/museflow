import asyncio
from contextlib import AsyncExitStack

from pydantic import EmailStr

import typer

from museflow.application.inputs.enricher import EnrichTracksConfigInput
from museflow.application.use_cases.tracks_enrich import EnrichTracksReport
from museflow.application.use_cases.tracks_enrich import tracks_enrich
from museflow.domain.exceptions import UserNotFound
from museflow.infrastructure.entrypoints.cli.commands.tracks import app
from museflow.infrastructure.entrypoints.cli.dependencies import get_db
from museflow.infrastructure.entrypoints.cli.dependencies import get_gemini_enricher
from museflow.infrastructure.entrypoints.cli.dependencies import get_track_repository
from museflow.infrastructure.entrypoints.cli.dependencies import get_user_repository
from museflow.infrastructure.entrypoints.cli.parsers import parse_email


@app.command("enrich", help="Enrich tracks with AI-inferred genre and mood metadata.")
def enrich(
    email: str = typer.Option(..., help="User email address.", parser=parse_email),
    force: bool = typer.Option(False, "--force", help="Re-enrich tracks that already have genre/mood data."),
    batch_size: int = typer.Option(200, "--batch-size", help="Number of tracks per Gemini request."),
    limit: int | None = typer.Option(None, "--limit", help="Maximum number of tracks to process."),
) -> None:
    try:
        result = asyncio.run(enrich_logic(email=email, force=force, batch_size=batch_size, limit=limit))
    except UserNotFound as e:
        raise typer.BadParameter(f"User not found with email: {email}") from e
    except Exception as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e

    if result.enriched_count == 0 and result.error_count == 0:
        typer.secho("No tracks to enrich.", fg=typer.colors.YELLOW)
        return

    typer.secho(f"Enriched {result.enriched_count} track(s).", fg=typer.colors.GREEN)
    if result.error_count:
        typer.secho(f"{result.error_count} batch(es) failed — check logs for details.", fg=typer.colors.YELLOW)


async def enrich_logic(
    email: EmailStr,
    force: bool = False,
    batch_size: int = 200,
    limit: int | None = None,
) -> EnrichTracksReport:
    config = EnrichTracksConfigInput(force=force, batch_size=batch_size, limit=limit)

    async with AsyncExitStack() as stack:
        session = await stack.enter_async_context(get_db())
        enricher = await stack.enter_async_context(get_gemini_enricher())
        user_repository = get_user_repository(session)
        track_repository = get_track_repository(session)

        user = await user_repository.get_by_email(email)
        if not user:
            raise UserNotFound()

        return await tracks_enrich(user, config, track_repository, enricher)
