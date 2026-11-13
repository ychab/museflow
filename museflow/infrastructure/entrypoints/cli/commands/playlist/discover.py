import asyncio
import math
from contextlib import AsyncExitStack

from pydantic import EmailStr

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from museflow.application.inputs.discovery import DiscoverTasteConfigInput
from museflow.application.use_cases.taste_discover import DiscoverTasteResult
from museflow.application.use_cases.taste_discover import DiscoverTasteUseCase
from museflow.domain.enums import DiscoveryFocus
from museflow.domain.enums import MusicProvider
from museflow.domain.exceptions import DiscoveryTrackNoNewError
from museflow.domain.exceptions import ProviderAuthTokenNotFoundError
from museflow.domain.exceptions import TasteProfileNotFoundError
from museflow.domain.exceptions import TasteProfileStatusNotReadyError
from museflow.domain.exceptions import UserNotFoundError
from museflow.infrastructure.adapters.common.llm.usage import LLMUsageMeter
from museflow.infrastructure.config.settings.app import app_settings
from museflow.infrastructure.entrypoints.cli.commands.playlist import app
from museflow.infrastructure.entrypoints.cli.dependencies import get_advisor
from museflow.infrastructure.entrypoints.cli.dependencies import get_provider_library
from museflow.infrastructure.entrypoints.cli.dependencies import get_unit_of_work
from museflow.infrastructure.entrypoints.cli.options import EMAIL_OPTION
from museflow.infrastructure.entrypoints.cli.utils.display import print_llm_usage
from museflow.infrastructure.entrypoints.cli.utils.display import spinner

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
    limit: int = typer.Option(
        DiscoverTasteConfigInput.playlist_limit,
        "--limit",
        help="Target number of tracks in the generated playlist",
        min=1,
        max=30,
    ),
) -> None:
    """Discover new tracks guided by your AI taste profile."""
    meter = LLMUsageMeter()
    try:
        with spinner("Discovering tracks…"):
            result = asyncio.run(
                playlist_discover_logic(
                    email=email,
                    provider=provider,
                    model=model,
                    config=DiscoverTasteConfigInput(
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
                border_style="blue",
            )
        )

        report_table = Table(title="Discovery Report")
        report_table.add_column("Attempt", justify="right")
        report_table.add_column("Artists", justify="right")
        report_table.add_column("Unknown tracks", justify="right")
        report_table.add_column("Picked", justify="right")
        for report in result.reports:
            report_table.add_row(
                str(report.attempt),
                str(report.artists),
                str(report.candidates),
                str(report.tracks_picked),
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
                f"\n\nSuggested tracks successfully saved into playlist '{result.playlist.name}'! ✅",
                fg=typer.colors.GREEN,
            )
            typer.secho(f"Saved playlist ID: {result.playlist.id}", fg=typer.colors.CYAN)
            typer.secho(
                f"  View it: museflow playlist view {result.playlist.id}",
                fg=typer.colors.CYAN,
            )
            typer.secho(
                "  Rate tracks: museflow rate playlist --play",
                fg=typer.colors.CYAN,
            )
    finally:
        print_llm_usage(meter)


async def playlist_discover_logic(
    email: EmailStr,
    provider: MusicProvider,
    config: DiscoverTasteConfigInput,
    model: str | None = None,
    meter: LLMUsageMeter | None = None,
) -> DiscoverTasteResult:
    """Discovers new music guided by the user's taste profile and creates a playlist.

    Args:
        email: The email of the user.
        provider: The music provider to use for search and playlist creation.
        config: The configuration for the discovery process.
        model: An OpenRouter model id overriding the configured advisor model.
        meter: Collects the tokens and cost of the advisor calls.

    Returns:
        A DiscoverTasteResult with the playlist, strategy, reports, and final tracks.

    Raises:
        UserNotFoundError: If the user with the given email is not found.
        ProviderAuthTokenNotFoundError: If the user's auth token for the provider is not found.
        TasteProfileNotFoundError: If no matching taste profile is found.
    """
    async with AsyncExitStack() as stack:
        uow = get_unit_of_work()

        async with uow:
            user = await uow.users.get_by_email(email)
            if not user:
                raise UserNotFoundError()

        provider_library = await stack.enter_async_context(get_provider_library(provider, user=user, uow=uow))

        advisor = await stack.enter_async_context(get_advisor(model, meter=meter))

        use_case = DiscoverTasteUseCase(
            uow=uow,
            provider_library=provider_library,
            advisor=advisor,
        )

        return await use_case.create_suggestions_playlist(user=user, config=config)
