import asyncio
import time
from contextlib import AsyncExitStack
from pathlib import Path

from pydantic import EmailStr

import typer
from rich.table import Table

from museflow.application.inputs.history import ImportStreamingHistoryConfigInput
from museflow.application.use_cases.import_streaming_history import ImportStreamingHistoryReport
from museflow.application.use_cases.import_streaming_history import ImportStreamingHistoryUseCase
from museflow.domain.exceptions import ProviderAuthTokenNotFoundError
from museflow.domain.exceptions import StreamingHistoryException
from museflow.domain.exceptions import UserNotFound
from museflow.domain.types import MusicProvider
from museflow.infrastructure.entrypoints.cli.commands.spotify import app
from museflow.infrastructure.entrypoints.cli.commands.spotify import console
from museflow.infrastructure.entrypoints.cli.dependencies import get_auth_token_repository
from museflow.infrastructure.entrypoints.cli.dependencies import get_db
from museflow.infrastructure.entrypoints.cli.dependencies import get_spotify_client
from museflow.infrastructure.entrypoints.cli.dependencies import get_spotify_library_factory
from museflow.infrastructure.entrypoints.cli.dependencies import get_track_repository
from museflow.infrastructure.entrypoints.cli.dependencies import get_user_repository
from museflow.infrastructure.entrypoints.cli.parsers import parse_email


@app.command("history", help="Import Spotify extended streaming history from JSON files.")
def history(
    email: str = typer.Option(..., help="User email address", parser=parse_email),
    directory: Path = typer.Option(
        ...,
        "--directory",
        help="Directory containing Spotify streaming history JSON files",
    ),
    min_duration_played: int = typer.Option(
        90, "--min-duration-played", help="Minimum duration played in seconds to include"
    ),
    batch_size: int = typer.Option(
        20,
        "--batch-size",
        help="Number of tracks to fetch concurrently and upsert per batch",
        min=1,
        max=50,
    ),
    purge: bool = typer.Option(False, "--purge/--no-purge", help="Purge existing HISTORY tracks before import"),
) -> None:
    start_time = time.perf_counter()

    config = ImportStreamingHistoryConfigInput(
        directory=directory,
        min_ms_played=min_duration_played * 1_000,
        batch_size=batch_size,
        purge=purge,
    )

    try:
        report = asyncio.run(history_logic(email=email, config=config))
    except UserNotFound as e:
        raise typer.BadParameter(f"User not found with email: {email}") from e
    except ProviderAuthTokenNotFoundError as e:
        typer.secho(
            f"Auth token not found with email: {email}. Did you forget to connect?", fg=typer.colors.RED, err=True
        )
        raise typer.Exit(code=1) from e
    except StreamingHistoryException as e:
        typer.secho(str(e), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e
    except Exception as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e

    end_time = time.perf_counter()
    duration = end_time - start_time

    typer.secho(f"\nImport successful in {duration:.2f}s!\n", fg=typer.colors.GREEN)

    table = Table(title="Import Streaming History Results")
    table.add_column("Label", style="cyan")
    table.add_column("Value", justify="right", style="magenta")

    table.add_row("Items read", str(report.items_read))
    table.add_row("Items skipped (duration)", str(report.items_skipped_duration))
    table.add_row("Items skipped (no URI)", str(report.items_skipped_no_uri))
    table.add_row("Unique track IDs", str(report.unique_track_ids))
    table.add_row("Tracks already known", str(report.tracks_already_known))
    table.add_row("Tracks fetched", str(report.tracks_fetched))
    table.add_row("Tracks created", str(report.tracks_created))

    console.print(table)


async def history_logic(email: EmailStr, config: ImportStreamingHistoryConfigInput) -> ImportStreamingHistoryReport:
    async with AsyncExitStack() as stack:
        session = await stack.enter_async_context(get_db())
        spotify_client = await stack.enter_async_context(get_spotify_client())
        spotify_library_factory = get_spotify_library_factory(
            session=session,
            spotify_client=spotify_client,
        )

        user_repository = get_user_repository(session)
        auth_token_repository = get_auth_token_repository(session)
        track_repository = get_track_repository(session)

        user = await user_repository.get_by_email(email)
        if user is None:
            raise UserNotFound()

        auth_token = await auth_token_repository.get(user_id=user.id, provider=MusicProvider.SPOTIFY)
        if auth_token is None:
            raise ProviderAuthTokenNotFoundError()

        spotify_library = spotify_library_factory.create(user=user, auth_token=auth_token)

        use_case = ImportStreamingHistoryUseCase(
            provider_library=spotify_library,
            track_repository=track_repository,
        )
        return await use_case.import_history(user=user, config=config)
