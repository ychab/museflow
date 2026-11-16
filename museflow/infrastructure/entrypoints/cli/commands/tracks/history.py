import asyncio
import time
from datetime import timedelta
from pathlib import Path

from pydantic import EmailStr

import typer
from rich.table import Table

from museflow.application.inputs.history import ImportStreamingHistoryConfigInput
from museflow.application.ports.progress import ProgressPort
from museflow.application.use_cases.history_import import ImportStreamingHistoryReport
from museflow.application.use_cases.history_import import ImportStreamingHistoryUseCase
from museflow.domain.enums import MusicProvider
from museflow.domain.exceptions import StreamingHistoryError
from museflow.domain.exceptions import UserNotFoundError
from museflow.infrastructure.adapters.progress.rich import RichProgressAdapter
from museflow.infrastructure.config.loggers import console_stderr
from museflow.infrastructure.entrypoints.cli.commands.tracks import app
from museflow.infrastructure.entrypoints.cli.commands.tracks import console
from museflow.infrastructure.entrypoints.cli.dependencies import get_streaming_history_adapter
from museflow.infrastructure.entrypoints.cli.dependencies import get_unit_of_work
from museflow.infrastructure.entrypoints.cli.options import EMAIL_OPTION
from museflow.infrastructure.entrypoints.cli.utils.display import has_rich_log_handler
from museflow.infrastructure.utils.formatting import format_duration


@app.command("history", help="Import extended streaming history from JSON files.")
def tracks_history_command(
    email: str = EMAIL_OPTION,
    directory: Path = typer.Option(
        ...,
        "--directory",
        help="Directory containing streaming history JSON files",
    ),
    provider: MusicProvider = typer.Option(
        MusicProvider.SPOTIFY, "--provider", help="Music provider to import streaming history from"
    ),
    min_duration_played: int = typer.Option(
        ImportStreamingHistoryConfigInput.min_ms_played // 1_000,
        "--min-duration-played",
        help="Minimum duration played in seconds to include",
    ),
    batch_size: int = typer.Option(
        ImportStreamingHistoryConfigInput.batch_size,
        "--batch-size",
        help="Number of tracks to upsert per batch",
        min=1,
        max=500,
    ),
    purge: bool = typer.Option(False, "--purge/--no-purge", help="Purge existing tracks before import"),
) -> None:
    start_time = time.perf_counter()

    config = ImportStreamingHistoryConfigInput(
        directory=directory,
        min_ms_played=min_duration_played * 1_000,
        batch_size=batch_size,
        purge=purge,
    )

    try:
        with RichProgressAdapter(console=console_stderr, animated=has_rich_log_handler()) as progress:
            report = asyncio.run(
                tracks_history_logic(email=email, config=config, provider=provider, progress=progress)
            )
    except UserNotFoundError as e:
        raise typer.BadParameter(f"User not found with email: {email}") from e
    except StreamingHistoryError as e:
        typer.secho(str(e), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e
    except Exception as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e

    duration = timedelta(seconds=time.perf_counter() - start_time)

    typer.secho(f"\nImport successful in {format_duration(duration)}!\n", fg=typer.colors.GREEN)

    table = Table(title="Import Streaming History Results")
    table.add_column("Label", style="cyan")
    table.add_column("Value", justify="right", style="magenta")

    table.add_row("Items read", str(report.items_read))
    table.add_row("Items skipped (no timestamp)", str(report.items_skipped_no_timestamp))
    table.add_row("Items skipped (short play)", str(report.items_skipped_short_play))
    table.add_row("Items skipped (no track ID)", str(report.items_skipped_no_track_id))
    table.add_row("Unique track IDs", str(report.unique_track_ids))
    table.add_row("Tracks already known", str(report.tracks_already_known))
    table.add_row("Total play events", str(report.plays_total))
    table.add_row("Play events created", str(report.plays_created))
    table.add_row("Tracks created", str(report.tracks_created))

    console.print(table)


async def tracks_history_logic(
    email: EmailStr,
    config: ImportStreamingHistoryConfigInput,
    provider: MusicProvider,
    progress: ProgressPort,
) -> ImportStreamingHistoryReport:
    uow = get_unit_of_work()

    async with uow:
        user = await uow.users.get_by_email(email)

    if not user:
        raise UserNotFoundError()

    use_case = ImportStreamingHistoryUseCase(
        uow=uow, streaming_history=get_streaming_history_adapter(provider), progress=progress
    )
    return await use_case.import_history(user=user, config=config)
