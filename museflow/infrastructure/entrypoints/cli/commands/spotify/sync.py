import asyncio
import time
from contextlib import AsyncExitStack

from pydantic import EmailStr

import typer
from rich.table import Table

from museflow.application.use_cases.provider_sync_library import ProviderSyncLibraryUseCase
from museflow.application.use_cases.provider_sync_library import SyncConfigInput
from museflow.application.use_cases.provider_sync_library import SyncReport
from museflow.domain.exceptions import ProviderAuthTokenNotFoundError
from museflow.domain.exceptions import UserNotFound
from museflow.domain.types import MusicProvider
from museflow.infrastructure.adapters.providers.spotify.types import SpotifyTimeRange
from museflow.infrastructure.entrypoints.cli.commands.spotify import app
from museflow.infrastructure.entrypoints.cli.commands.spotify import console
from museflow.infrastructure.entrypoints.cli.dependencies import get_artist_repository
from museflow.infrastructure.entrypoints.cli.dependencies import get_auth_token_repository
from museflow.infrastructure.entrypoints.cli.dependencies import get_db
from museflow.infrastructure.entrypoints.cli.dependencies import get_spotify_library_factory
from museflow.infrastructure.entrypoints.cli.dependencies import get_spotify_oauth
from museflow.infrastructure.entrypoints.cli.dependencies import get_track_repository
from museflow.infrastructure.entrypoints.cli.dependencies import get_user_repository
from museflow.infrastructure.entrypoints.cli.parsers import parse_email


@app.command("sync", help="Synchronize the Spotify user's items.")
def sync(
    email: str = typer.Option(..., help="User email address", parser=parse_email),
    purge_all: bool = typer.Option(
        False,
        "--purge-all/--no-purge-all",
        help="Whether to purge all user's items",
    ),
    purge_artist_top: bool = typer.Option(
        False,
        "--purge-artist-top/--no-purge-artist-top",
        help="Whether to purge user's top artists",
    ),
    purge_track_top: bool = typer.Option(
        False,
        "--purge-track-top/--no-purge-track-top",
        help="Whether to purge user's top tracks",
    ),
    purge_track_saved: bool = typer.Option(
        False,
        "--purge-track-saved/--no-purge-track-saved",
        help="Whether to purge user's saved tracks",
    ),
    purge_track_playlist: bool = typer.Option(
        False,
        "--purge-track-playlist/--no-purge-track-playlist",
        help="Whether to purge user's playlist tracks",
    ),
    sync_all: bool = typer.Option(
        False,
        "--sync-all/--no-sync-all",
        help="Whether to sync all user's items",
    ),
    sync_artist_top: bool = typer.Option(
        False,
        "--sync-artist-top/--no-sync-artist-top",
        help="Whether to sync user's top artists",
    ),
    sync_track_top: bool = typer.Option(
        False,
        "--sync-track-top/--no-sync-track-top",
        help="Whether to sync user's top tracks",
    ),
    sync_track_saved: bool = typer.Option(
        False,
        "--sync-track-saved/--no-sync-track-saved",
        help="Whether to sync user's saved tracks",
    ),
    sync_track_playlist: bool = typer.Option(
        False,
        "--sync-track-playlist/--no-sync-track-playlist",
        help="Whether to sync user's playlist tracks",
    ),
    page_size: int = typer.Option(
        50,
        "--page-size",
        help="How many items to fetch per page",
        min=1,
        max=50,
    ),
    time_range: SpotifyTimeRange = typer.Option(
        "long_term",
        "--time-range",
        help="The time range of the items to fetch (top artist and top tracks)",
    ),
    batch_size: int = typer.Option(
        300,
        "--batch-size",
        help="The number of items to bulk upsert in DB",
        min=1,
        max=500,
    ),
) -> None:
    """
    Synchronize the Spotify user's items into the database, including artists and tracks.
    """
    start_time = time.perf_counter()

    config = SyncConfigInput(
        purge_all=purge_all,
        purge_artist_top=purge_artist_top,
        purge_track_top=purge_track_top,
        purge_track_saved=purge_track_saved,
        purge_track_playlist=purge_track_playlist,
        sync_all=sync_all,
        sync_artist_top=sync_artist_top,
        sync_track_top=sync_track_top,
        sync_track_saved=sync_track_saved,
        sync_track_playlist=sync_track_playlist,
        page_size=page_size,
        time_range=time_range,
        batch_size=batch_size,
    )
    if not config.has_purge() and not config.has_sync():
        typer.secho("At least one flag must be provided.", fg=typer.colors.RED, err=True)
        raise typer.Abort()

    try:
        report = asyncio.run(sync_logic(email=email, config=config))
    except UserNotFound as e:
        raise typer.BadParameter(f"User not found with email: {email}") from e
    except ProviderAuthTokenNotFoundError as e:
        typer.secho(
            f"Auth token not found with email: {email}. Did you forget to connect?", fg=typer.colors.RED, err=True
        )
        raise typer.Exit(code=1) from e
    except Exception as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e

    if report.has_errors:
        for error in report.errors:
            typer.secho(error, fg=typer.colors.RED, err=True)
        raise typer.Abort()

    end_time = time.perf_counter()
    duration = end_time - start_time

    typer.secho(f"\nSynchronization successful in {duration:.2f}s!\n", fg=typer.colors.GREEN)

    table = Table(title="Sync Results")
    table.add_column("Label", style="cyan")
    table.add_column("Value", justify="right", style="magenta")

    table.add_row("Artists purged", str(report.purge_artist))
    table.add_row("Artists created", str(report.artist_created))
    table.add_row("Artists updated", str(report.artist_updated))
    table.add_row("Tracks purged", str(report.purge_track))
    table.add_row("Tracks created", str(report.track_created))
    table.add_row("Tracks updated", str(report.track_updated))

    console.print(table)


async def sync_logic(email: EmailStr, config: SyncConfigInput) -> SyncReport:
    async with AsyncExitStack() as stack:
        session = await stack.enter_async_context(get_db())

        spotify_client = await stack.enter_async_context(get_spotify_oauth())
        spotify_library_factory = get_spotify_library_factory(
            session=session,
            spotify_client=spotify_client,
        )

        user_repository = get_user_repository(session)
        auth_token_repository = get_auth_token_repository(session)
        artist_repository = get_artist_repository(session)
        track_repository = get_track_repository(session)

        user = await user_repository.get_by_email(email)
        if user is None:
            raise UserNotFound()

        auth_token = await auth_token_repository.get(user_id=user.id, provider=MusicProvider.SPOTIFY)
        if auth_token is None:
            raise ProviderAuthTokenNotFoundError()

        spotify_library = spotify_library_factory.create(user=user, auth_token=auth_token)

        use_case = ProviderSyncLibraryUseCase(
            provider_library=spotify_library,
            artist_repository=artist_repository,
            track_repository=track_repository,
        )
        return await use_case.sync_library(
            user=user,
            config=config,
        )
