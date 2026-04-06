import asyncio
from contextlib import AsyncExitStack

from pydantic import EmailStr

import typer

from museflow.application.inputs.taste import BuildTasteProfileConfigInput
from museflow.application.use_cases.build_taste_profile import BuildTasteProfileUseCase
from museflow.domain.entities.taste import TasteProfile
from museflow.domain.exceptions import TasteProfileNoSeedException
from museflow.domain.exceptions import UserNotFound
from museflow.infrastructure.entrypoints.cli.commands.taste import app
from museflow.infrastructure.entrypoints.cli.dependencies import get_db
from museflow.infrastructure.entrypoints.cli.dependencies import get_gemini_profiler
from museflow.infrastructure.entrypoints.cli.dependencies import get_taste_profile_repository
from museflow.infrastructure.entrypoints.cli.dependencies import get_track_repository
from museflow.infrastructure.entrypoints.cli.dependencies import get_user_repository
from museflow.infrastructure.entrypoints.cli.parsers import parse_email


@app.command("build", help="Build a master taste profile from your library.")
def build(
    email: str = typer.Option(..., help="User email address", parser=parse_email),
    track_limit: int = typer.Option(
        3000,
        "--track-limit",
        help="Max seed tracks to build the profile",
        min=1,
        max=20000,
    ),
    batch_size: int = typer.Option(
        400,
        "--batch-size",
        help="Batch sizes for profiles",
        min=1,
        max=1000,
    ),
) -> None:
    try:
        profile = asyncio.run(build_logic(email=email, track_limit=track_limit, batch_size=batch_size))
    except UserNotFound as e:
        raise typer.BadParameter(f"User not found with email: {email}") from e
    except TasteProfileNoSeedException as e:
        typer.secho("No tracks found for this user. Import your library first.", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e
    except Exception as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e

    typer.secho(f"\nTaste profile built: {profile.tracks_count} tracks processed", fg=typer.colors.GREEN)
    typer.echo(f"Profiler: {profile.profiler} ({profile.logic_version})")
    typer.echo(f"Eras: {len(profile.profile['taste_timeline'])}")
    if profile.profile["personality_archetype"]:
        typer.secho(f"Archetype: {profile.profile['personality_archetype']}", fg=typer.colors.CYAN)
    for insight in profile.profile["life_phase_insights"]:
        typer.echo(f"  - {insight}")


async def build_logic(email: EmailStr, track_limit: int, batch_size: int) -> TasteProfile:
    async with AsyncExitStack() as stack:
        session = await stack.enter_async_context(get_db())
        profiler = await stack.enter_async_context(get_gemini_profiler())

        user_repository = get_user_repository(session)
        track_repository = get_track_repository(session)
        taste_profile_repository = get_taste_profile_repository(session)

        user = await user_repository.get_by_email(email)
        if user is None:
            raise UserNotFound()

        use_case = BuildTasteProfileUseCase(
            profiler=profiler,
            track_repository=track_repository,
            taste_profile_repository=taste_profile_repository,
        )
        config = BuildTasteProfileConfigInput(track_limit=track_limit, batch_size=batch_size)

        return await use_case.build_profile(user=user, config=config)
