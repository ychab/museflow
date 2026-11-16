import asyncio
from contextlib import AsyncExitStack
from typing import Final

from pydantic import EmailStr

import typer
from rich.console import Group
from rich.panel import Panel
from rich.text import Text

from museflow.application.inputs.taste import BuildTasteProfileConfigInput
from museflow.application.ports.progress import ProgressPort
from museflow.application.use_cases.taste_profile_build import BuildTasteProfileUseCase
from museflow.domain.const import TASTE_BATCH_COUNT_TARGET
from museflow.domain.const import TASTE_BATCH_SIZE_MIN
from museflow.domain.entities.taste import TasteProfile
from museflow.domain.exceptions import TasteProfileBuildPausedError
from museflow.domain.exceptions import TasteProfileNoSeedError
from museflow.domain.exceptions import UserNotFoundError
from museflow.infrastructure.adapters.common.llm.usage import LLMUsageMeter
from museflow.infrastructure.adapters.progress.rich import RichProgressAdapter
from museflow.infrastructure.config.loggers import console_stderr
from museflow.infrastructure.config.settings.app import app_settings
from museflow.infrastructure.entrypoints.cli.commands.taste import app
from museflow.infrastructure.entrypoints.cli.dependencies import get_profiler
from museflow.infrastructure.entrypoints.cli.dependencies import get_unit_of_work
from museflow.infrastructure.entrypoints.cli.options import EMAIL_OPTION
from museflow.infrastructure.entrypoints.cli.options import VERBOSE_OPTION
from museflow.infrastructure.entrypoints.cli.utils.display import console
from museflow.infrastructure.entrypoints.cli.utils.display import has_rich_log_handler
from museflow.infrastructure.entrypoints.cli.utils.display import print_llm_usage


@app.command("build", help="Build a master taste profile from your library.")
def taste_build_command(
    email: str = EMAIL_OPTION,
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
    batch_size: int | None = typer.Option(
        BuildTasteProfileConfigInput.batch_size,
        "--batch-size",
        help=(
            f"Seed tracks per listening period (one LLM request each). Default: {TASTE_BATCH_SIZE_MIN}, or the seeds "
            f"split into about {TASTE_BATCH_COUNT_TARGET} periods for a larger library"
        ),
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
    verbose: bool = VERBOSE_OPTION,
) -> None:
    meter = LLMUsageMeter()
    try:
        with RichProgressAdapter(console=console_stderr, meter=meter, animated=has_rich_log_handler()) as progress:
            profile = asyncio.run(
                taste_build_logic(
                    email=email,
                    name=name,
                    resume=resume,
                    rated_only=rated_only,
                    track_limit=track_limit,
                    batch_size=batch_size,
                    segment_model=segment_model,
                    merge_model=merge_model,
                    reflect_model=reflect_model,
                    meter=meter,
                    progress=progress,
                )
            )
    except UserNotFoundError as e:
        raise typer.BadParameter(f"User not found with email: {email}") from e
    except TasteProfileNoSeedError as e:
        typer.secho("No tracks found for this user. Import your library first.", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e
    except TasteProfileBuildPausedError as e:
        typer.secho(
            f"Build paused at batch {e.batch_index}/{e.total_batches}: {e.reason}\nRun with --resume to continue.",
            fg=typer.colors.YELLOW,
            err=True,
        )
        raise typer.Exit(code=1) from e
    except KeyboardInterrupt as e:
        # Each period done was checkpointed in its own transaction: --resume picks up after it
        typer.secho(
            "Build interrupted: the periods done are saved. Run with --resume to continue.",
            fg=typer.colors.YELLOW,
            err=True,
        )
        raise typer.Exit(code=130) from e
    except Exception as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e
    else:
        _print_profile(profile)
    finally:
        print_llm_usage(meter, verbose=verbose)


async def taste_build_logic(
    email: EmailStr,
    name: str,
    track_limit: int,
    batch_size: int | None,
    resume: bool,
    rated_only: bool,
    progress: ProgressPort,
    segment_model: str | None = None,
    merge_model: str | None = None,
    reflect_model: str | None = None,
    meter: LLMUsageMeter | None = None,
) -> TasteProfile:
    async with AsyncExitStack() as stack:
        profiler_adapter = await stack.enter_async_context(
            get_profiler(segment_model, merge_model, reflect_model, meter=meter)
        )

        uow = get_unit_of_work()
        async with uow:
            user = await uow.users.get_by_email(email)
        if user is None:
            raise UserNotFoundError()

        use_case = BuildTasteProfileUseCase(uow=uow, profiler=profiler_adapter, progress=progress)
        config = BuildTasteProfileConfigInput(
            name=name,
            resume=resume,
            rated_only=rated_only,
            track_limit=track_limit,
            batch_size=batch_size,
            throttling_sleep_seconds=app_settings.TASTE_PROFILE_BUILD_THROTTLING_SLEEP_SECONDS,
        )

        return await use_case.build_profile(user=user, config=config)


_STEPS_ORDER: Final[tuple[str, ...]] = ("segment", "merge", "reflect")


def _print_profile(profile: TasteProfile) -> None:
    """Prints the built profile: its archetype, eras and insights in a panel, then the model of each step."""
    data = profile.profile
    eras = data["taste_timeline"]
    # Text, not markup: an AI-written label may hold brackets
    lines: list[Text] = []
    if data["personality_archetype"]:
        lines.append(Text(data["personality_archetype"], style="bold cyan"))
    lines.append(
        Text(f"{profile.tracks_count} tracks · {len(eras)} eras · logic {profile.logic_version}", style="dim")
    )
    if eras:
        lines.append(Text())
        lines.extend(Text.assemble((f"{era['time_range']:<9}", "dim"), "  ", era["era_label"]) for era in eras)
    if data["life_phase_insights"]:
        lines.append(Text())
        lines.extend(Text(f"• {insight}") for insight in data["life_phase_insights"])

    console.print(
        Panel(
            Group(*lines),
            title=Text.assemble(("✓ ", "green"), f"Taste profile '{profile.name}'"),
            title_align="left",
            border_style="green",
        )
    )
    # In the pipeline's order: JSONB, where the profile is saved, reorders the keys
    steps = profile.profiler_metadata["steps"]
    models = " · ".join(f"{step} {steps[step]['model']}" for step in _STEPS_ORDER if step in steps)
    console.print(Text(f"Models: {models}", style="dim"))
