import asyncio
from contextlib import AsyncExitStack

from pydantic import EmailStr

import typer

from museflow.application.inputs.enrich import EnrichTracksConfigInput
from museflow.application.use_cases.tracks_enrich import EnrichTracksReport
from museflow.application.use_cases.tracks_enrich import tracks_enrich
from museflow.domain.enums import EnrichField
from museflow.domain.exceptions import UserNotFound
from museflow.infrastructure.entrypoints.cli.commands.enrich import app
from museflow.infrastructure.entrypoints.cli.dependencies import get_db
from museflow.infrastructure.entrypoints.cli.dependencies import get_gemini_enricher
from museflow.infrastructure.entrypoints.cli.dependencies import get_track_repository
from museflow.infrastructure.entrypoints.cli.dependencies import get_user_repository
from museflow.infrastructure.entrypoints.cli.parsers import parse_email


@app.command("tracks", help="Enrich tracks with AI-inferred genre, mood, and locale metadata.")
def enrich(
    email: str = typer.Option(..., help="User email address.", parser=parse_email),
    only_genre: bool = typer.Option(False, "--only-genre", help="Enrich genre tags only."),
    only_mood: bool = typer.Option(False, "--only-mood", help="Enrich mood labels only."),
    only_locale: bool = typer.Option(False, "--only-locale", help="Enrich locale only."),
    force: bool = typer.Option(False, "--force", help="Re-enrich tracks that already have the requested fields."),
    batch_size: int = typer.Option(200, "--batch-size", help="Number of tracks per Gemini request."),
    limit: int | None = typer.Option(None, "--limit", help="Maximum number of tracks to process."),
) -> None:
    try:
        result = asyncio.run(
            enrich_logic(
                email=email,
                only_genre=only_genre,
                only_mood=only_mood,
                only_locale=only_locale,
                force=force,
                batch_size=batch_size,
                limit=limit,
            )
        )
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
    only_genre: bool = False,
    only_mood: bool = False,
    only_locale: bool = False,
    force: bool = False,
    batch_size: int = 200,
    limit: int | None = None,
) -> EnrichTracksReport:
    selected = {
        f
        for f, flag in [
            (EnrichField.GENRE, only_genre),
            (EnrichField.MOOD, only_mood),
            (EnrichField.LOCALE, only_locale),
        ]
        if flag
    }
    fields = frozenset(selected) if selected else frozenset(EnrichField)

    config = EnrichTracksConfigInput(fields=fields, force=force, batch_size=batch_size, limit=limit)

    async with AsyncExitStack() as stack:
        session = await stack.enter_async_context(get_db())
        enricher = await stack.enter_async_context(get_gemini_enricher())
        user_repository = get_user_repository(session)
        track_repository = get_track_repository(session)

        user = await user_repository.get_by_email(email)
        if not user:
            raise UserNotFound()

        return await tracks_enrich(user, config, track_repository, enricher)
