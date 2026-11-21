import math
from contextlib import AsyncExitStack
from typing import Annotated

from pydantic import EmailStr

import typer

from museflow.application.inputs.explore import CreateExplorationPlaylistConfigInput
from museflow.application.ports.progress import ProgressPort
from museflow.application.use_cases.playlist_exploration_create import CreateExplorationPlaylistResult
from museflow.application.use_cases.playlist_exploration_create import CreateExplorationPlaylistUseCase
from museflow.application.use_cases.user_get import get_user
from museflow.domain.enums import MusicProvider
from museflow.domain.exceptions import DiscoveryTrackNoNewError
from museflow.domain.exceptions import ProviderAuthTokenNotFoundError
from museflow.domain.exceptions import UserNotFoundError
from museflow.infrastructure.adapters.common.llm.usage import LLMUsageMeter
from museflow.infrastructure.adapters.progress.rich import RichProgressAdapter
from museflow.infrastructure.config.loggers.setup import console_stderr
from museflow.infrastructure.config.settings.app import app_settings
from museflow.infrastructure.entrypoints.cli.commands.playlist import app
from museflow.infrastructure.entrypoints.cli.dependencies import get_wiring
from museflow.infrastructure.entrypoints.cli.dependencies import run_logic
from museflow.infrastructure.entrypoints.cli.options import EmailOption
from museflow.infrastructure.entrypoints.cli.options import VerboseOption
from museflow.infrastructure.entrypoints.cli.utils.display import has_rich_log_handler
from museflow.infrastructure.entrypoints.cli.utils.display import print_llm_usage
from museflow.infrastructure.entrypoints.cli.utils.display import print_playlist_outcome


@app.command("explore")
def playlist_explore_command(
    *,
    prompt: Annotated[
        str | None,
        typer.Argument(
            help="Optional request on the sound wanted (e.g. 'calm and acoustic'); the artists still come from your data"
        ),
    ] = None,
    email: EmailOption,
    provider: Annotated[MusicProvider, typer.Option(help="The music provider to use")] = MusicProvider.SPOTIFY,
    model: Annotated[
        str | None,
        typer.Option(
            "--model",
            help="OpenRouter model id overriding the configured advisor model (e.g. google/gemini-3.5-flash).",
        ),
    ] = None,
    title: Annotated[
        str | None, typer.Option("--title", help="Playlist name, used as is (defaults to 'Explore' with a timestamp)")
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run", help="Explore tracks without creating a playlist (still searches the provider catalogue)"
        ),
    ] = False,
    verbose: VerboseOption = False,
    limit: Annotated[
        int, typer.Option("--limit", help="Target number of tracks in the generated playlist", min=1, max=30)
    ] = CreateExplorationPlaylistConfigInput.playlist_limit,
) -> None:
    """Play the tracks you don't know from your favourite artists, drawn from your ratings and plays."""
    meter = LLMUsageMeter()
    try:
        with RichProgressAdapter(
            console=console_stderr, meter=meter, animated=has_rich_log_handler(), verbose=verbose
        ) as progress:
            result = run_logic(
                playlist_explore_logic(
                    email=email,
                    provider=provider,
                    model=model,
                    config=CreateExplorationPlaylistConfigInput(
                        prompt=prompt,
                        title=title,
                        artists_limit=app_settings.EXPLORE_ARTISTS_LIMIT,
                        artists_per_attempt=app_settings.EXPLORE_ARTISTS_PER_ATTEMPT,
                        ratings_confidence=app_settings.STATS_BAYESIAN_CONFIDENCE,
                        picks_limit=math.ceil(limit * app_settings.DISCOVERY_ADVISOR_LIMIT_RATIO),
                        catalogue_tracks_pages=app_settings.DISCOVERY_REQUESTED_ARTIST_TRACKS_PAGES,
                        artist_tracks_concurrency=app_settings.EXPLORE_ARTISTS_CONCURRENCY,
                        playlist_limit=limit,
                        max_attempts=app_settings.DISCOVERY_MAX_ATTEMPTS,
                        max_tracks_per_artist=app_settings.DISCOVERY_MAX_TRACKS_PER_ARTIST,
                        liked_tracks_score_threshold=app_settings.DISCOVERY_LIKED_SCORE_THRESHOLD,
                        liked_tracks_limit=app_settings.DISCOVERY_LIKED_TRACKS_LIMIT,
                        dry_run=dry_run,
                    ),
                    meter=meter,
                    progress=progress,
                ),
            )
    except UserNotFoundError as e:
        raise typer.BadParameter(f"User not found with email: {email}") from e
    except ProviderAuthTokenNotFoundError as e:
        typer.secho(
            f"Auth token not found with email: {email}. Did you forget to connect?", fg=typer.colors.RED, err=True
        )
        raise typer.Exit(code=1) from e
    except DiscoveryTrackNoNewError as e:
        typer.secho(
            "No new tracks found: rate tracks or import your history, so that your favourite artists are known",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1) from e
    except Exception as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e
    else:
        print_playlist_outcome(
            tracks=result.tracks,
            playlist=result.playlist,
            target=limit,
            hint="rate more tracks, so that more favourite artists are known.",
        )
    finally:
        print_llm_usage(meter, verbose=verbose)


async def playlist_explore_logic(
    email: EmailStr,
    provider: MusicProvider,
    config: CreateExplorationPlaylistConfigInput,
    progress: ProgressPort,
    model: str | None = None,
    meter: LLMUsageMeter | None = None,
) -> CreateExplorationPlaylistResult:
    """Explores the catalogue of the user's favourite artists and creates a playlist of the tracks they don't know.

    Raises:
        UserNotFoundError: If the user with the given email is not found.
        ProviderAuthTokenNotFoundError: If the user's auth token for the provider is not found.
    """
    async with AsyncExitStack() as stack:
        wiring = get_wiring()
        uow = wiring.build_unit_of_work()

        user = await get_user(email=email, uow=uow)

        provider_library = await stack.enter_async_context(wiring.build_provider_library(provider, user=user, uow=uow))
        advisor = await stack.enter_async_context(wiring.build_advisor(model, meter=meter))

        use_case = CreateExplorationPlaylistUseCase(
            uow=uow, provider_library=provider_library, advisor=advisor, progress=progress
        )
        return await use_case.create_playlist(user=user, config=config)
