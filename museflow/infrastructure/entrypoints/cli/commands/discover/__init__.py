import typer

app = typer.Typer()

import museflow.infrastructure.entrypoints.cli.commands.discover.create  # noqa: E402,F401
import museflow.infrastructure.entrypoints.cli.commands.discover.list_  # noqa: E402,F401
import museflow.infrastructure.entrypoints.cli.commands.discover.rate  # noqa: E402,F401
import museflow.infrastructure.entrypoints.cli.commands.discover.view  # noqa: E402,F401
