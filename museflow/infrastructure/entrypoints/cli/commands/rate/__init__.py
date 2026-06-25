import typer

app = typer.Typer()

import museflow.infrastructure.entrypoints.cli.commands.rate.export  # noqa: F401,E402
import museflow.infrastructure.entrypoints.cli.commands.rate.history  # noqa: F401,E402
import museflow.infrastructure.entrypoints.cli.commands.rate.import_  # noqa: F401,E402
import museflow.infrastructure.entrypoints.cli.commands.rate.playlist  # noqa: F401,E402
