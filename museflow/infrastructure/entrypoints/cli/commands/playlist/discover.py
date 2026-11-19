import math
from contextlib import AsyncExitStack

from pydantic import EmailStr

import typer
from rich.console import Console
from rich.panel import Panel

from museflow.application.inputs.discovery import CreateDiscoveryPlaylistConfigInput
from museflow.application.ports.progress import ProgressPort
from museflow.application.use_cases.playlist_discovery_create import CreateDiscoveryPlaylistResult
from museflow.application.use_cases.playlist_discovery_create import CreateDiscoveryPlaylistUseCase
from museflow.application.use_cases.user_get import get_user
from museflow.domain.enums import DiscoveryFocus
from museflow.domain.enums import MusicProvider
from museflow.domain.exceptions import DiscoveryTrackNoNewError
from museflow.domain.exceptions import ProviderAuthTokenNotFoundError
from museflow.domain.exceptions import TasteProfileNotFoundError
from museflow.domain.exceptions import TasteProfileStatusNotReadyError
from museflow.domain.exceptions import UserNotFoundError
from museflow.infrastructure.adapters.common.llm.usage import LLMUsageMeter
from museflow.infrastructure.adapters.progress.rich import RichProgressAdapter
from museflow.infrastructure.config.loggers.setup import console_stderr
from museflow.infrastructure.config.settings.app import app_settings
from museflow.infrastructure.entrypoints.cli.commands.playlist import app
from museflow.infrastructure.entrypoints.cli.dependencies import get_unit_of_work
from museflow.infrastructure.entrypoints.cli.dependencies import run_logic
from museflow.infrastructure.entrypoints.cli.options import EMAIL_OPTION
from museflow.infrastructure.entrypoints.cli.options import VERBOSE_OPTION
from museflow.infrastructure.entrypoints.cli.utils.display import has_rich_log_handler
from museflow.infrastructure.entrypoints.cli.utils.display import print_llm_usage
from museflow.infrastructure.entrypoints.cli.utils.display import print_playlist_outcome
from museflow.infrastructure.entrypoints.wiring import build_advisor
from museflow.infrastructure.entrypoints.wiring import build_provider_library

console = Console()


@app.command("discover")
def playlist_discover_command(
    prompt: str | None = typer.Argument(
        None,
        help="Optional freeform request for the advisor: genres, moods, a theme (e.g. 'lo-fi jazz and soul for focus')",
    ),
    email: str = EMAIL_OPTION,
    provider: MusicProvider = typer.Option(default=MusicProvider.SPOTIFY, help="The music provider to use"),
    name: str | None = typer.Option(None, "--name", help="Taste profile name (defaults to latest)"),
    focus: DiscoveryFocus | None = typer.Option(
        None,
        "--focus",
        help="The discovery focus strategy (defaults to expansion without a prompt, none with one)",
    ),
    model: str | None = typer.Option(
        None,
        "--model",
        help="OpenRouter model id overriding the configured advisor model (e.g. google/gemini-3.5-flash).",
    ),
    title: str | None = typer.Option(
        None,
        "--title",
        help="Playlist name, used as is (defaults to the advisor's suggestion with a timestamp)",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Discover tracks without creating a playlist (still searches the provider catalogue)",
    ),
    verbose: bool = VERBOSE_OPTION,
    limit: int = typer.Option(
        CreateDiscoveryPlaylistConfigInput.playlist_limit,
        "--limit",
        help="Target number of tracks in the generated playlist",
        min=1,
        max=30,
    ),
) -> None:
    """Discover new tracks guided by your AI taste profile."""
    meter = LLMUsageMeter()
    try:
        with RichProgressAdapter(
            console=console_stderr, meter=meter, animated=has_rich_log_handler(), verbose=verbose
        ) as progress:
            result = run_logic(
                playlist_discover_logic(
                    email=email,
                    provider=provider,
                    model=model,
                    config=CreateDiscoveryPlaylistConfigInput(
                        prompt=prompt,
                        focus=focus,
                        profile_name=name,
                        title=title,
                        advisor_limit=math.ceil(limit * app_settings.DISCOVERY_ADVISOR_LIMIT_RATIO),
                        artist_tracks_pages=app_settings.DISCOVERY_ARTIST_TRACKS_PAGES,
                        requested_artist_tracks_pages=app_settings.DISCOVERY_REQUESTED_ARTIST_TRACKS_PAGES,
                        liked_tracks_score_threshold=app_settings.DISCOVERY_LIKED_SCORE_THRESHOLD,
                        liked_tracks_limit=app_settings.DISCOVERY_LIKED_TRACKS_LIMIT,
                        disliked_tracks_score_threshold=app_settings.DISCOVERY_DISLIKED_SCORE_THRESHOLD,
                        disliked_tracks_limit=app_settings.DISCOVERY_DISLIKED_TRACKS_LIMIT,
                        covered_artists_limit=app_settings.DISCOVERY_COVERED_ARTISTS_LIMIT,
                        playlist_limit=limit,
                        max_attempts=app_settings.DISCOVERY_MAX_ATTEMPTS,
                        max_tracks_per_artist=app_settings.DISCOVERY_MAX_TRACKS_PER_ARTIST,
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
    except TasteProfileNotFoundError as e:
        typer.secho("No profile found. Run `museflow taste build --name <name>` first.", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e
    except TasteProfileStatusNotReadyError as e:
        typer.secho(
            "Taste profile is still being built. Run `museflow taste build` to completion first.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1) from e
    except DiscoveryTrackNoNewError as e:
        typer.secho("No new tracks found after all attempts", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e
    except Exception as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e
    else:
        console.print(
            Panel(
                result.strategy.reasoning,
                title=result.strategy.strategy_label,
                title_align="left",
                border_style="blue",
            )
        )
        console.print()
        print_playlist_outcome(
            tracks=result.tracks,
            playlist=result.playlist,
            target=limit,
            hint="a broader prompt or another --focus usually finds more.",
        )
    finally:
        print_llm_usage(meter, verbose=verbose)


async def playlist_discover_logic(
    email: EmailStr,
    provider: MusicProvider,
    config: CreateDiscoveryPlaylistConfigInput,
    progress: ProgressPort,
    model: str | None = None,
    meter: LLMUsageMeter | None = None,
) -> CreateDiscoveryPlaylistResult:
    """Discovers new music guided by the user's taste profile and creates a playlist.

    Args:
        email: The email of the user.
        provider: The music provider to use for search and playlist creation.
        config: The configuration for the discovery process.
        progress: Follows the steps as they run.
        model: An OpenRouter model id overriding the configured advisor model.
        meter: Collects the tokens and cost of the advisor calls.

    Returns:
        A CreateDiscoveryPlaylistResult with the playlist, strategy, and final tracks.

    Raises:
        UserNotFoundError: If the user with the given email is not found.
        ProviderAuthTokenNotFoundError: If the user's auth token for the provider is not found.
        TasteProfileNotFoundError: If no matching taste profile is found.
    """
    async with AsyncExitStack() as stack:
        uow = get_unit_of_work()

        user = await get_user(email=email, uow=uow)

        provider_library = await stack.enter_async_context(
            build_provider_library(provider, user=user, uow=uow, token_uow=get_unit_of_work())
        )

        advisor = await stack.enter_async_context(build_advisor(model, meter=meter))

        use_case = CreateDiscoveryPlaylistUseCase(
            uow=uow,
            provider_library=provider_library,
            advisor=advisor,
            progress=progress,
        )

        return await use_case.create_playlist(user=user, config=config)
