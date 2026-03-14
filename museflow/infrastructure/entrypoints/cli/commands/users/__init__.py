import typer

app = typer.Typer()

import museflow.infrastructure.entrypoints.cli.commands.users.create  # noqa: F401,E402
import museflow.infrastructure.entrypoints.cli.commands.users.update  # noqa: F401,E402
