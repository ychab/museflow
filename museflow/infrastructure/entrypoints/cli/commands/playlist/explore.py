import asyncio
import math
from contextlib import AsyncExitStack

from pydantic import EmailStr

import typer
from rich.console import Console
from rich.table import Table

from museflow.application.inputs.explore import ExploreArtistsConfigInput
from museflow.application.use_cases.artists_explore import ExploreArtistsResult
from museflow.application.use_cases.artists_explore import ExploreArtistsUseCase
from museflow.domain.enums import MusicProvider
from museflow.domain.exceptions import DiscoveryTrackNoNewError
from museflow.domain.exceptions import ProviderAuthTokenNotFoundError
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


@app.command("explore")
def playlist_explore_command(
    prompt: str | None = typer.Argument(
        None,
        help="Optional request on the sound wanted (e.g. 'calm and acoustic'); the artists still come from your data",
    ),
    email: str = EMAIL_OPTION,
    provider: MusicProvider = typer.Option(default=MusicProvider.SPOTIFY, help="The music provider to use"),
    model: str | None = typer.Option(
        None,
        "--model",
        help="OpenRouter model id overriding the configured advisor model (e.g. google/gemini-3.5-flash).",
    ),
    title: str | None = typer.Option(
        None,
        "--title",
        help="Playlist name, used as is (defaults to 'Explore' with a timestamp)",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Explore tracks without creating a playlist (still searches the provider catalogue)",
    ),
    limit: int = typer.Option(
        ExploreArtistsConfigInput.playlist_limit,
        "--limit",
        help="Target number of tracks in the generated playlist",
        min=1,
        max=30,
    ),
) -> None:
    """Play the tracks you don't know from your favourite artists, drawn from your ratings and plays."""
    meter = LLMUsageMeter()
    try:
        with spinner("Exploring your artists…"):
            result = asyncio.run(
                playlist_explore_logic(
                    email=email,
                    provider=provider,
                    model=model,
                    config=ExploreArtistsConfigInput(
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
        report_table = Table(title="Exploration Report")
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
            track_table.add_row(str(i), ", ".join(track.artists), track.name, track.album_name or "")
        console.print(track_table)

        if result.playlist is None:
            typer.secho("\n\nTracks explored but playlist not created (dry-run mode) ⚠️", fg=typer.colors.YELLOW)
        else:
            typer.secho(
                f"\n\nExplored tracks successfully saved into playlist '{result.playlist.name}'! ✅",
                fg=typer.colors.GREEN,
            )
            typer.secho(f"Saved playlist ID: {result.playlist.id}", fg=typer.colors.CYAN)
            typer.secho(f"  View it: museflow playlist view {result.playlist.id}", fg=typer.colors.CYAN)
            typer.secho("  Rate tracks: museflow rate playlist --play", fg=typer.colors.CYAN)
    finally:
        print_llm_usage(meter)


async def playlist_explore_logic(
    email: EmailStr,
    provider: MusicProvider,
    config: ExploreArtistsConfigInput,
    model: str | None = None,
    meter: LLMUsageMeter | None = None,
) -> ExploreArtistsResult:
    """Explores the catalogue of the user's favourite artists and creates a playlist of the tracks they don't know.

    Raises:
        UserNotFoundError: If the user with the given email is not found.
        ProviderAuthTokenNotFoundError: If the user's auth token for the provider is not found.
    """
    async with AsyncExitStack() as stack:
        uow = get_unit_of_work()

        async with uow:
            user = await uow.users.get_by_email(email)
            if not user:
                raise UserNotFoundError()

        provider_library = await stack.enter_async_context(get_provider_library(provider, user=user, uow=uow))
        advisor = await stack.enter_async_context(get_advisor(model, meter=meter))

        use_case = ExploreArtistsUseCase(uow=uow, provider_library=provider_library, advisor=advisor)
        return await use_case.create_playlist(user=user, config=config)
