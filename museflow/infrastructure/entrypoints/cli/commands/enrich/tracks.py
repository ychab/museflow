import asyncio
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any

from pydantic import EmailStr
from pydantic import TypeAdapter

import typer

from museflow.application.inputs.enrich import EnrichmentEntryInput
from museflow.application.inputs.enrich import EnrichTracksConfigInput
from museflow.application.use_cases.tracks_enrich import EnrichTracksReport
from museflow.application.use_cases.tracks_enrich import EnrichTracksUseCase
from museflow.domain.enums import EnrichField
from museflow.domain.exceptions import TrackEnrichmentAbortedError
from museflow.domain.exceptions import UserNotFoundError
from museflow.infrastructure.adapters.common.llm.usage import LLMUsageMeter
from museflow.infrastructure.entrypoints.cli.commands.enrich import app
from museflow.infrastructure.entrypoints.cli.dependencies import get_enricher
from museflow.infrastructure.entrypoints.cli.dependencies import get_unit_of_work
from museflow.infrastructure.entrypoints.cli.options import EMAIL_OPTION
from museflow.infrastructure.entrypoints.cli.utils.display import print_llm_usage
from museflow.infrastructure.entrypoints.cli.utils.display import spinner
from museflow.infrastructure.entrypoints.cli.utils.files import read_yaml


@app.command("tracks", help="Enrich tracks with AI-inferred genre, mood, and locales (sung languages) metadata.")
def enrich_tracks_command(
    email: str = EMAIL_OPTION,
    only_genre: bool = typer.Option(False, "--only-genre", help="Enrich genre tags only."),
    only_mood: bool = typer.Option(False, "--only-mood", help="Enrich mood labels only."),
    only_locale: bool = typer.Option(False, "--only-locale", help="Enrich locales (sung languages) only."),
    input_path: Path | None = typer.Option(
        None,
        "--input",
        help="YAML file listing the tracks to enrich by fingerprint, as written by `enrich export` (e.g. a sample).",
    ),
    force: bool = typer.Option(False, "--force", help="Re-enrich tracks that already have the requested fields."),
    batch_size: int = typer.Option(
        EnrichTracksConfigInput.batch_size,
        "--batch-size",
        help="Number of tracks per LLM request.",
    ),
    model: str | None = typer.Option(
        None,
        "--model",
        help="OpenRouter model id overriding the configured enricher model (e.g. google/gemini-3.1-flash-lite).",
    ),
    limit: int | None = typer.Option(None, "--limit", help="Maximum number of tracks to process."),
) -> None:
    data = read_yaml(input_path) if input_path is not None else None

    meter = LLMUsageMeter()
    try:
        with spinner("Enriching tracks…"):
            result = asyncio.run(
                enrich_tracks_logic(
                    email=email,
                    only_genre=only_genre,
                    only_mood=only_mood,
                    only_locale=only_locale,
                    data=data,
                    force=force,
                    batch_size=batch_size,
                    model=model,
                    limit=limit,
                    meter=meter,
                )
            )
    except UserNotFoundError as e:
        raise typer.BadParameter(f"User not found with email: {email}") from e
    except TrackEnrichmentAbortedError as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        if force:
            typer.secho("With --force, a new run starts over from the first track.", fg=typer.colors.YELLOW, err=True)
        else:
            typer.secho(
                "Run the command again to continue: tracks already enriched are skipped.",
                fg=typer.colors.YELLOW,
                err=True,
            )
        raise typer.Exit(code=1) from e
    except Exception as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e
    else:
        if result.not_found_count:
            typer.secho(
                f"{result.not_found_count} fingerprint(s) of the input match no track.",
                fg=typer.colors.YELLOW,
                err=True,
            )
        if result.enriched_count == 0 and result.error_count == 0:
            typer.secho("No tracks to enrich.", fg=typer.colors.YELLOW)
            return

        if result.enriched_count == 0:
            typer.secho(
                f"No track enriched: {result.error_count} batch(es) failed — check logs for details.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(code=1)

        typer.secho(f"Enriched {result.enriched_count} track(s).", fg=typer.colors.GREEN)
        if result.error_count:
            typer.secho(f"{result.error_count} batch(es) failed — check logs for details.", fg=typer.colors.YELLOW)
    finally:
        print_llm_usage(meter)


async def enrich_tracks_logic(
    email: EmailStr,
    only_genre: bool = False,
    only_mood: bool = False,
    only_locale: bool = False,
    data: list[Any] | None = None,
    force: bool = False,
    batch_size: int = 200,
    model: str | None = None,
    limit: int | None = None,
    meter: LLMUsageMeter | None = None,
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

    fingerprints = None
    if data is not None:
        entries = TypeAdapter(list[EnrichmentEntryInput]).validate_python(data)
        fingerprints = list(dict.fromkeys(entry.fingerprint for entry in entries))

    config = EnrichTracksConfigInput(
        fields=fields,
        fingerprints=fingerprints,
        force=force,
        batch_size=batch_size,
        limit=limit,
    )

    async with AsyncExitStack() as stack:
        enricher = await stack.enter_async_context(get_enricher(model=model, meter=meter))

        uow = get_unit_of_work()
        async with uow:
            user = await uow.users.get_by_email(email)

        if not user:
            raise UserNotFoundError()

        use_case = EnrichTracksUseCase(uow=uow, track_enricher=enricher)
        return await use_case.enrich(user=user, config=config)
