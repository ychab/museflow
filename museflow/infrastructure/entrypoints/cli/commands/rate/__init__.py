import typer

app = typer.Typer()

import museflow.infrastructure.entrypoints.cli.commands.rate.history  # noqa: F401,E402
import museflow.infrastructure.entrypoints.cli.commands.rate.playlist  # noqa: F401,E402
import museflow.infrastructure.entrypoints.cli.commands.rate.track  # noqa: F401,E402
