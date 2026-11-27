from contextlib import AsyncExitStack
from datetime import timedelta
from typing import Annotated
from typing import Final

from pydantic import EmailStr

import typer
from rich.console import Group
from rich.panel import Panel
from rich.text import Text

from museflow.application.inputs.taste import BuildTasteProfileConfigInput
from museflow.application.ports.progress import ProgressPort
from museflow.application.use_cases.taste_profile_build import BuildTasteProfileUseCase
from museflow.application.use_cases.user_get import get_user
from museflow.domain.const import TASTE_BATCH_COUNT_TARGET
from museflow.domain.const import TASTE_BATCH_SIZE_MIN
from museflow.domain.const import TASTE_PROFILE_NAME_MAX_LENGTH
from museflow.domain.entities.taste import TasteProfile
from museflow.domain.exceptions import TasteProfileBuildPausedError
from museflow.domain.exceptions import TasteProfileNoSeedError
from museflow.domain.exceptions import UserNotFoundError
from museflow.domain.utils.text import slugify
from museflow.infrastructure.adapters.common.llm.usage import LLMUsageMeter
from museflow.infrastructure.adapters.progress.rich import RichProgressAdapter
from museflow.infrastructure.config.loggers.setup import console_stderr
from museflow.infrastructure.config.settings.app import app_settings
from museflow.infrastructure.entrypoints.cli.commands.taste import app
from museflow.infrastructure.entrypoints.cli.dependencies import get_wiring
from museflow.infrastructure.entrypoints.cli.dependencies import run_logic
from museflow.infrastructure.entrypoints.cli.options import EmailOption
from museflow.infrastructure.entrypoints.cli.options import VerboseOption
from museflow.infrastructure.entrypoints.cli.parsers import parse_taste_profile_name
from museflow.infrastructure.entrypoints.cli.utils.display import console
from museflow.infrastructure.entrypoints.cli.utils.display import has_rich_log_handler
from museflow.infrastructure.entrypoints.cli.utils.display import print_llm_usage


@app.command("build", help="Build a master taste profile from your library.")
def taste_build_command(
    email: EmailOption,
    title: Annotated[str, typer.Option("--title", help='Profile title, as shown (e.g. "Soirées d\'hiver")')],
    name: Annotated[
        str | None,
        typer.Option(
            "--name",
            help="Profile name keying it, unique per user: letters, digits, '-' and '_'. Default: the title as a slug",
            parser=parse_taste_profile_name,
            show_default=False,
        ),
    ] = None,
    resume: Annotated[bool, typer.Option("--resume/--no-resume", help="Resume from last checkpoint")] = False,
    rated_only: Annotated[
        bool,
        typer.Option(
            "--rated-only/--no-rated-only",
            help="Restrict seed tracks to only those the user has explicitly rated (score 0–10)",
        ),
    ] = False,
    track_limit: Annotated[
        int, typer.Option("--track-limit", help="Max seed tracks to build the profile", min=1, max=20000)
    ] = BuildTasteProfileConfigInput.track_limit,
    batch_size: Annotated[
        int | None,
        typer.Option(
            "--batch-size",
            help=(
                f"Seed tracks per listening period (one LLM request each). Default: {TASTE_BATCH_SIZE_MIN}, or the seeds "
                f"split into about {TASTE_BATCH_COUNT_TARGET} periods for a larger library"
            ),
            min=1,
            max=1000,
        ),
    ] = BuildTasteProfileConfigInput.batch_size,
    segment_model: Annotated[
        str | None,
        typer.Option(
            "--segment-model",
            help="OpenRouter model id overriding the configured segment step model (e.g. google/gemini-3.1-flash-lite).",
        ),
    ] = None,
    merge_model: Annotated[
        str | None,
        typer.Option("--merge-model", help="OpenRouter model id overriding the configured merge step model."),
    ] = None,
    reflect_model: Annotated[
        str | None,
        typer.Option("--reflect-model", help="OpenRouter model id overriding the configured reflect step model."),
    ] = None,
    verbose: VerboseOption = False,
) -> None:
    name = name or slugify(title, max_length=TASTE_PROFILE_NAME_MAX_LENGTH)
    if not name:
        raise typer.BadParameter("needs a letter or a digit, or pass --name", param_hint="'--title'")

    meter = LLMUsageMeter()
    try:
        with RichProgressAdapter(console=console_stderr, meter=meter, animated=has_rich_log_handler()) as progress:
            profile = run_logic(
                taste_build_logic(
                    email=email,
                    name=name,
                    title=title,
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
    title: str,
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
        wiring = get_wiring()
        profiler_adapter = await stack.enter_async_context(
            wiring.build_profiler(segment_model, merge_model, reflect_model, meter=meter)
        )

        uow = wiring.build_unit_of_work()
        user = await get_user(email=email, uow=uow)

        use_case = BuildTasteProfileUseCase(uow=uow, profiler=profiler_adapter, progress=progress)
        config = BuildTasteProfileConfigInput(
            name=name,
            title=title,
            resume=resume,
            rated_only=rated_only,
            track_limit=track_limit,
            batch_size=batch_size,
            throttling_sleep_seconds=app_settings.TASTE_PROFILE_BUILD_THROTTLING_SLEEP_SECONDS,
            lease_duration=timedelta(minutes=app_settings.TASTE_PROFILE_BUILD_LEASE_MINUTES),
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
            title=Text.assemble(("✓ ", "green"), f"Taste profile '{profile.title}' ({profile.name})"),
            title_align="left",
            border_style="green",
        )
    )
    # In the pipeline's order: JSONB, where the profile is saved, reorders the keys
    steps = profile.profiler_metadata["steps"]
    models = " · ".join(f"{step} {steps[step]['model']}" for step in _STEPS_ORDER if step in steps)
    console.print(Text(f"Models: {models}", style="dim"))
