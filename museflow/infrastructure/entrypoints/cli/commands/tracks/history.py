import time
import uuid
from datetime import timedelta
from pathlib import Path
from typing import Annotated

from pydantic import EmailStr

import typer
from rich.table import Table

from museflow.application.inputs.history import ImportStreamingHistoryConfigInput
from museflow.application.ports.progress import ProgressPort
from museflow.application.use_cases.track_history_archive_extract import extract_history_archive
from museflow.application.use_cases.track_history_import import ImportStreamingHistoryReport
from museflow.application.use_cases.track_history_import import ImportStreamingHistoryUseCase
from museflow.application.use_cases.user_get import get_user
from museflow.domain.enums import MusicProvider
from museflow.domain.exceptions import ArchiveError
from museflow.domain.exceptions import StreamingHistoryError
from museflow.domain.exceptions import StreamingHistoryFilesNotFoundError
from museflow.domain.exceptions import UserNotFoundError
from museflow.infrastructure.adapters.progress.rich import RichProgressAdapter
from museflow.infrastructure.config.loggers.setup import console_stderr
from museflow.infrastructure.entrypoints.cli.commands.tracks import app
from museflow.infrastructure.entrypoints.cli.commands.tracks import console
from museflow.infrastructure.entrypoints.cli.dependencies import get_wiring
from museflow.infrastructure.entrypoints.cli.dependencies import run_logic
from museflow.infrastructure.entrypoints.cli.options import EmailOption
from museflow.infrastructure.entrypoints.cli.utils.display import has_rich_log_handler
from museflow.infrastructure.utils.formatting import format_duration


@app.command(
    "history",
    help="Import extended streaming history: the zip archive of the export, or a directory of its JSON files.",
)
def tracks_history_command(
    email: EmailOption,
    archive: Annotated[
        Path | None,
        typer.Option("--archive", help="Zip archive of the export, as delivered", exists=True, dir_okay=False),
    ] = None,
    directory: Annotated[
        Path | None,
        typer.Option(
            "--directory", help="Directory containing streaming history JSON files", exists=True, file_okay=False
        ),
    ] = None,
    provider: Annotated[
        MusicProvider, typer.Option("--provider", help="Music provider to import streaming history from")
    ] = MusicProvider.SPOTIFY,
    min_duration_played: Annotated[
        int, typer.Option("--min-duration-played", help="Minimum duration played in seconds to include")
    ] = ImportStreamingHistoryConfigInput.min_ms_played // 1_000,
    batch_size: Annotated[
        int, typer.Option("--batch-size", help="Number of tracks to upsert per batch", min=1, max=500)
    ] = ImportStreamingHistoryConfigInput.batch_size,
    purge: Annotated[bool, typer.Option("--purge/--no-purge", help="Purge existing tracks before import")] = False,
) -> None:
    # Typer has no exclusive options: one of the two, and only one
    source = archive or directory
    if source is None or (archive is not None and directory is not None):
        raise typer.BadParameter("Give either --archive or --directory")

    start_time = time.perf_counter()

    config = ImportStreamingHistoryConfigInput(
        prefix=f"history/{uuid.uuid4()}",
        min_ms_played=min_duration_played * 1_000,
        batch_size=batch_size,
        purge=purge,
    )

    try:
        with RichProgressAdapter(console=console_stderr, animated=has_rich_log_handler()) as progress:
            report = run_logic(
                tracks_history_logic(
                    email=email,
                    source=source,
                    config=config,
                    provider=provider,
                    progress=progress,
                )
            )
    except UserNotFoundError as e:
        raise typer.BadParameter(f"User not found with email: {email}") from e
    except (ArchiveError, StreamingHistoryError) as e:
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
    source: Path,
    config: ImportStreamingHistoryConfigInput,
    provider: MusicProvider,
    progress: ProgressPort,
) -> ImportStreamingHistoryReport:
    """Puts the export files into the user's file storage, extracted from the source when it is an archive, copied
    from it when it is a directory, imports them, then deletes them.

    The CLI reads the files through the storage like the worker does with an upload: one import path for both.
    """
    wiring = get_wiring()
    uow = wiring.build_unit_of_work()
    streaming_history = wiring.build_streaming_history(provider)
    file_storage = wiring.build_file_storage()

    user = await get_user(email=email, uow=uow)

    use_case = ImportStreamingHistoryUseCase(
        uow=uow,
        streaming_history=streaming_history,
        file_storage=file_storage,
        progress=progress,
    )
    try:
        if source.is_dir():
            paths = sorted(source.glob(streaming_history.file_pattern))
            if not paths:
                raise StreamingHistoryFilesNotFoundError(
                    f"No {streaming_history.file_pattern} files found in: {source}"
                )

            for path in paths:
                await file_storage.put(user_id=user.id, key=f"{config.prefix}/{path.name}", content=path.read_bytes())
        else:
            await extract_history_archive(
                user=user,
                archive=source.read_bytes(),
                prefix=config.prefix,
                file_storage=file_storage,
                archive_reader=wiring.build_archive_reader(),
                streaming_history=streaming_history,
            )

        report = await use_case.import_history(user=user, config=config)
    finally:
        await file_storage.delete(user_id=user.id, prefix=config.prefix)

    return report
