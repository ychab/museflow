import asyncio
import time
from contextlib import AsyncExitStack
from pathlib import Path

from pydantic import EmailStr

import typer
from rich.table import Table

from museflow.application.inputs.history import StreamingHistoryImportConfigInput
from museflow.application.use_cases.history_import import ImportStreamingHistoryReport
from museflow.application.use_cases.history_import import ImportStreamingHistoryUseCase
from museflow.domain.enums import MusicProvider
from museflow.domain.exceptions import StreamingHistoryException
from museflow.domain.exceptions import UserNotFound
from museflow.infrastructure.entrypoints.cli.commands.tracks import app
from museflow.infrastructure.entrypoints.cli.commands.tracks import console
from museflow.infrastructure.entrypoints.cli.dependencies import get_db
from museflow.infrastructure.entrypoints.cli.dependencies import get_streaming_history_adapter
from museflow.infrastructure.entrypoints.cli.dependencies import get_track_repository
from museflow.infrastructure.entrypoints.cli.dependencies import get_user_repository
from museflow.infrastructure.entrypoints.cli.parsers import parse_email


@app.command("history", help="Import extended streaming history from JSON files.")
def history(
    email: str = typer.Option(..., help="User email address", parser=parse_email),
    directory: Path = typer.Option(
        ...,
        "--directory",
        help="Directory containing streaming history JSON files",
    ),
    provider: MusicProvider = typer.Option(
        MusicProvider.SPOTIFY, "--provider", help="Music provider to import streaming history from"
    ),
    min_duration_played: int = typer.Option(
        90, "--min-duration-played", help="Minimum duration played in seconds to include"
    ),
    batch_size: int = typer.Option(
        20,
        "--batch-size",
        help="Number of tracks to upsert per batch",
        min=1,
        max=500,
    ),
    purge: bool = typer.Option(False, "--purge/--no-purge", help="Purge existing tracks before import"),
) -> None:
    start_time = time.perf_counter()

    config = StreamingHistoryImportConfigInput(
        directory=directory,
        min_ms_played=min_duration_played * 1_000,
        batch_size=batch_size,
        purge=purge,
    )

    try:
        report = asyncio.run(history_logic(email=email, config=config, provider=provider))
    except UserNotFound as e:
        raise typer.BadParameter(f"User not found with email: {email}") from e
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
    table.add_row("Items skipped (no timestamp)", str(report.items_skipped_no_timestamp))
    table.add_row("Items skipped (short play)", str(report.items_skipped_short_play))
    table.add_row("Items skipped (no track ID)", str(report.items_skipped_no_track_id))
    table.add_row("Unique track IDs", str(report.unique_track_ids))
    table.add_row("Tracks already known", str(report.tracks_already_known))
    table.add_row("Tracks play data updated", str(report.tracks_played_at_updated))
    table.add_row("Total play events", str(report.plays_total))
    table.add_row("Tracks created", str(report.tracks_created))

    console.print(table)


async def history_logic(
    email: EmailStr, config: StreamingHistoryImportConfigInput, provider: MusicProvider
) -> ImportStreamingHistoryReport:
    async with AsyncExitStack() as stack:
        session = await stack.enter_async_context(get_db())

        user_repository = get_user_repository(session)
        track_repository = get_track_repository(session)

        user = await user_repository.get_by_email(email)
        if user is None:
            raise UserNotFound()

        use_case = ImportStreamingHistoryUseCase(
            track_repository=track_repository,
            streaming_history=get_streaming_history_adapter(provider),
        )
        return await use_case.import_history(user=user, config=config)
