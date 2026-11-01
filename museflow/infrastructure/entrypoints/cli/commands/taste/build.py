import asyncio
from contextlib import AsyncExitStack

from pydantic import EmailStr

import typer

from museflow.application.inputs.taste import BuildTasteProfileConfigInput
from museflow.application.use_cases.taste_profile_build import BuildTasteProfileUseCase
from museflow.domain.entities.taste import TasteProfile
from museflow.domain.exceptions import TasteProfileBuildPausedException
from museflow.domain.exceptions import TasteProfileNoSeedException
from museflow.domain.exceptions import UserNotFound
from museflow.infrastructure.config.settings.app import app_settings
from museflow.infrastructure.entrypoints.cli.commands.taste import app
from museflow.infrastructure.entrypoints.cli.dependencies import get_profiler
from museflow.infrastructure.entrypoints.cli.dependencies import get_unit_of_work
from museflow.infrastructure.entrypoints.cli.parsers import parse_email


@app.command("build", help="Build a master taste profile from your library.")
def build(
    email: str = typer.Option(..., help="User email address", parser=parse_email),
    name: str = typer.Option(..., "--name", help="Profile name (unique per user)"),
    resume: bool = typer.Option(False, "--resume/--no-resume", help="Resume from last checkpoint"),
    rated_only: bool = typer.Option(
        False,
        "--rated-only/--no-rated-only",
        help="Restrict seed tracks to only those the user has explicitly rated (score 0–10)",
    ),
    track_limit: int = typer.Option(
        BuildTasteProfileConfigInput.track_limit,
        "--track-limit",
        help="Max seed tracks to build the profile",
        min=1,
        max=20000,
    ),
    batch_size: int = typer.Option(
        BuildTasteProfileConfigInput.batch_size,
        "--batch-size",
        help="Batch sizes for profiles",
        min=1,
        max=1000,
    ),
    segment_model: str | None = typer.Option(
        None,
        "--segment-model",
        help="OpenRouter model id overriding the configured segment step model (e.g. google/gemini-3.1-flash-lite).",
    ),
    merge_model: str | None = typer.Option(
        None,
        "--merge-model",
        help="OpenRouter model id overriding the configured merge step model.",
    ),
    reflect_model: str | None = typer.Option(
        None,
        "--reflect-model",
        help="OpenRouter model id overriding the configured reflect step model.",
    ),
) -> None:
    try:
        profile = asyncio.run(
            build_logic(
                email=email,
                name=name,
                resume=resume,
                rated_only=rated_only,
                track_limit=track_limit,
                batch_size=batch_size,
                segment_model=segment_model,
                merge_model=merge_model,
                reflect_model=reflect_model,
            )
        )
    except UserNotFound as e:
        raise typer.BadParameter(f"User not found with email: {email}") from e
    except TasteProfileNoSeedException as e:
        typer.secho("No tracks found for this user. Import your library first.", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e
    except TasteProfileBuildPausedException as e:
        typer.secho(
            f"Build paused at batch {e.batch_index}/{e.total_batches}: {e.reason}\nRun with --resume to continue.",
            fg=typer.colors.YELLOW,
            err=True,
        )
        raise typer.Exit(code=1) from e
    except Exception as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e

    typer.secho(f"\nTaste profile built: {profile.tracks_count} tracks processed", fg=typer.colors.GREEN)
    typer.echo(f"Name: {profile.name}")
    typer.echo(f"Logic version: {profile.logic_version}")
    for step, step_metadata in profile.profiler_metadata["steps"].items():
        typer.echo(f"Model ({step}): {step_metadata['model']}")
    typer.echo(f"Eras: {len(profile.profile['taste_timeline'])}")
    if profile.profile["personality_archetype"]:
        typer.secho(f"Archetype: {profile.profile['personality_archetype']}", fg=typer.colors.CYAN)
    for insight in profile.profile["life_phase_insights"]:
        typer.echo(f"  - {insight}")


async def build_logic(
    email: EmailStr,
    name: str,
    track_limit: int,
    batch_size: int,
    resume: bool,
    rated_only: bool,
    segment_model: str | None = None,
    merge_model: str | None = None,
    reflect_model: str | None = None,
) -> TasteProfile:
    async with AsyncExitStack() as stack:
        profiler_adapter = await stack.enter_async_context(get_profiler(segment_model, merge_model, reflect_model))

        uow = get_unit_of_work()
        async with uow:
            user = await uow.users.get_by_email(email)
        if user is None:
            raise UserNotFound()

        use_case = BuildTasteProfileUseCase(uow=uow, profiler=profiler_adapter)
        config = BuildTasteProfileConfigInput(
            name=name,
            resume=resume,
            rated_only=rated_only,
            track_limit=track_limit,
            batch_size=batch_size,
            throttling_sleep_seconds=app_settings.TASTE_PROFILE_BUILD_THROTTLING_SLEEP_SECONDS,
        )

        return await use_case.build_profile(user=user, config=config)
