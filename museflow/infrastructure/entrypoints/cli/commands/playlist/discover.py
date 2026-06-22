import asyncio
from contextlib import AsyncExitStack

from pydantic import EmailStr

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from museflow.application.inputs.discovery import DiscoverTasteConfigInput
from museflow.application.use_cases.taste_discover import DiscoverTasteResult
from museflow.application.use_cases.taste_discover import DiscoverTasteUseCase
from museflow.domain.exceptions import DiscoveryTrackNoNew
from museflow.domain.exceptions import ProviderAuthTokenNotFoundError
from museflow.domain.exceptions import TasteProfileNotFoundException
from museflow.domain.exceptions import TasteProfileStatusNotReadyException
from museflow.domain.exceptions import UserNotFound
from museflow.domain.types import DiscoveryFocus
from museflow.domain.types import MusicAdvisor
from museflow.domain.types import MusicProvider
from museflow.infrastructure.config.settings.app import app_settings
from museflow.infrastructure.entrypoints.cli.commands.playlist import app
from museflow.infrastructure.entrypoints.cli.dependencies import ADVISOR_TO_PROFILER
from museflow.infrastructure.entrypoints.cli.dependencies import get_advisor_adapter
from museflow.infrastructure.entrypoints.cli.dependencies import get_auth_token_repository
from museflow.infrastructure.entrypoints.cli.dependencies import get_blacklist_repository
from museflow.infrastructure.entrypoints.cli.dependencies import get_db
from museflow.infrastructure.entrypoints.cli.dependencies import get_playlist_repository
from museflow.infrastructure.entrypoints.cli.dependencies import get_provider_library_factory
from museflow.infrastructure.entrypoints.cli.dependencies import get_provider_oauth
from museflow.infrastructure.entrypoints.cli.dependencies import get_reconciler
from museflow.infrastructure.entrypoints.cli.dependencies import get_taste_profile_repository
from museflow.infrastructure.entrypoints.cli.dependencies import get_track_repository
from museflow.infrastructure.entrypoints.cli.dependencies import get_user_repository
from museflow.infrastructure.entrypoints.cli.parsers import parse_email

console = Console()


@app.command("discover")
def discover(
    email: str = typer.Option(..., help="User email address", parser=parse_email),
    advisor: MusicAdvisor = typer.Option(
        default=MusicAdvisor.GEMINI,
        help="The AI advisor to use",
    ),
    provider: MusicProvider = typer.Option(default=MusicProvider.SPOTIFY, help="The music provider to use"),
    focus: DiscoveryFocus = typer.Option(default=DiscoveryFocus.EXPANSION, help="The discovery focus strategy"),
    name: str | None = typer.Option(None, "--name", help="Taste profile name (defaults to latest)"),
    genre: str | None = typer.Option(None, "--genre", help="Optional genre hint for the advisor"),
    mood: str | None = typer.Option(None, "--mood", help="Optional mood hint for the advisor"),
    custom_instructions: str | None = typer.Option(
        None,
        "--custom-instructions",
        help="Optional freeform instructions for the advisor",
    ),
    advisor_limit: int = typer.Option(
        10,
        "--advisor-limit",
        help="Number of recommended tracks to request from the advisor",
        min=1,
        max=20,
    ),
    reconciler_limit: int = typer.Option(
        10,
        "--reconciler-limit",
        help="Maximum search candidates per suggestion",
        min=1,
        max=20,
    ),
    playlist_limit: int = typer.Option(
        10,
        "--playlist-limit",
        help="Target number of tracks in the generated playlist",
        min=1,
        max=30,
    ),
    max_attempts: int = typer.Option(
        3,
        "--max-attempts",
        help="Maximum number of advisor calls before stopping",
        min=1,
        max=10,
    ),
    max_tracks_per_artist: int = typer.Option(
        3,
        "--max-tracks-per-artist",
        help="Maximum tracks per artist in the final playlist",
        min=1,
        max=10,
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Discover tracks without creating a playlist",
    ),
) -> None:
    """Discover new tracks guided by your AI taste profile."""
    try:
        result = asyncio.run(
            discover_logic(
                email=email,
                advisor=advisor,
                provider=provider,
                config=DiscoverTasteConfigInput(
                    focus=focus,
                    profile_name=name,
                    genre=genre,
                    mood=mood,
                    custom_instructions=custom_instructions,
                    advisor_limit=advisor_limit,
                    reconciler_limit=reconciler_limit,
                    score_band_width=app_settings.DISCOVERY_SCORE_BAND_WIDTH,
                    liked_tracks_score_threshold=app_settings.DISCOVERY_LIKED_SCORE_THRESHOLD,
                    liked_tracks_limit=app_settings.DISCOVERY_LIKED_TRACKS_LIMIT,
                    playlist_limit=playlist_limit,
                    max_attempts=max_attempts,
                    max_tracks_per_artist=max_tracks_per_artist,
                    dry_run=dry_run,
                ),
            ),
        )
    except UserNotFound as e:
        raise typer.BadParameter(f"User not found with email: {email}") from e
    except ProviderAuthTokenNotFoundError as e:
        typer.secho(
            f"Auth token not found with email: {email}. Did you forget to connect?", fg=typer.colors.RED, err=True
        )
        raise typer.Exit(code=1) from e
    except TasteProfileNotFoundException as e:
        typer.secho("No profile found. Run muse taste build --name <name> first.", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e
    except TasteProfileStatusNotReadyException as e:
        typer.secho(
            "Taste profile is still being built. Run `muse taste build` to completion first.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1) from e
    except DiscoveryTrackNoNew as e:
        typer.secho("No new tracks found after all attempts", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e
    except Exception as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e

    console.print(
        Panel(
            result.strategy.reasoning,
            title=result.strategy.strategy_label,
            border_style="blue",
        )
    )

    report_table = Table(title="Discovery Report")
    report_table.add_column("Attempt", justify="right")
    report_table.add_column("Suggested", justify="right")
    report_table.add_column("Survived", justify="right")
    report_table.add_column("New", justify="right")
    for report in result.reports:
        report_table.add_row(
            str(report.attempt),
            str(report.tracks_suggested),
            str(report.tracks_survived),
            str(report.tracks_new),
        )
    console.print(report_table)

    track_table = Table(title=f"Tracks added to playlist{' (dry mode)' if dry_run else ''}")
    track_table.add_column("#", justify="right", style="dim")
    track_table.add_column("Artist(s)")
    track_table.add_column("Track")
    track_table.add_column("Album", style="dim")
    for i, track in enumerate(result.tracks, start=1):
        artists = ", ".join(track.artists)
        album_name = track.album_name or ""
        track_table.add_row(str(i), artists, track.name, album_name)
    console.print(track_table)

    if result.playlist is None:
        typer.secho(
            "\n\nTracks discovered but playlist not created (dry-run mode) ⚠️",
            fg=typer.colors.YELLOW,
        )
    else:
        typer.secho(
            f"\n\nSuggested tracks successfully saved into playlist '{result.strategy.suggested_playlist_name}'! ✅",
            fg=typer.colors.GREEN,
        )
        typer.secho(f"Saved playlist ID: {result.playlist.id}", fg=typer.colors.CYAN)
        typer.secho(
            f"  View it: museflow playlist view {result.playlist.id} --email {email}",
            fg=typer.colors.CYAN,
        )
        typer.secho(
            f"  Rate tracks: museflow rate playlist --email {email} --play",
            fg=typer.colors.CYAN,
        )


async def discover_logic(
    email: EmailStr,
    advisor: MusicAdvisor,
    provider: MusicProvider,
    config: DiscoverTasteConfigInput,
) -> DiscoverTasteResult:
    """Discovers new music guided by the user's taste profile and creates a playlist.

    Args:
        email: The email of the user.
        advisor: The AI advisor to use.
        provider: The music provider to use for search and playlist creation.
        config: The configuration for the discovery process.

    Returns:
        A DiscoverTasteResult with the playlist, strategy, reports, and final tracks.

    Raises:
        UserNotFound: If the user with the given email is not found.
        ProviderAuthTokenNotFoundError: If the user's auth token for the provider is not found.
        TasteProfileNotFoundException: If no matching taste profile is found.
    """
    profiler = ADVISOR_TO_PROFILER[advisor]

    async with AsyncExitStack() as stack:
        session = await stack.enter_async_context(get_db())

        user_repository = get_user_repository(session)
        auth_token_repository = get_auth_token_repository(session)
        track_repository = get_track_repository(session)
        taste_profile_repository = get_taste_profile_repository(session)
        blacklist_repository = get_blacklist_repository(session)
        playlist_repository = get_playlist_repository(session)

        provider_client = await stack.enter_async_context(get_provider_oauth(provider))
        provider_library_factory = get_provider_library_factory(
            provider=provider,
            session=session,
            oauth_client=provider_client,
        )

        advisor_adapter = await stack.enter_async_context(get_advisor_adapter(advisor))
        reconciler = get_reconciler()

        user = await user_repository.get_by_email(email)
        if not user:
            raise UserNotFound()

        auth_token = await auth_token_repository.get(user_id=user.id, provider=provider)
        if auth_token is None:
            raise ProviderAuthTokenNotFoundError()

        provider_library = provider_library_factory.create(user=user, auth_token=auth_token)

        use_case = DiscoverTasteUseCase(
            track_repository=track_repository,
            taste_profile_repository=taste_profile_repository,
            blacklist_repository=blacklist_repository,
            playlist_repository=playlist_repository,
            provider_library=provider_library,
            advisor=advisor_adapter,
            reconciler=reconciler,
            profiler=profiler,
        )

        return await use_case.create_suggestions_playlist(user=user, config=config)
