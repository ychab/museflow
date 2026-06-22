import typer

app = typer.Typer()

import museflow.infrastructure.entrypoints.cli.commands.playlist.delete  # noqa: E402,F401
import museflow.infrastructure.entrypoints.cli.commands.playlist.discover  # noqa: E402,F401
import museflow.infrastructure.entrypoints.cli.commands.playlist.list_  # noqa: E402,F401
import museflow.infrastructure.entrypoints.cli.commands.playlist.view  # noqa: E402,F401
