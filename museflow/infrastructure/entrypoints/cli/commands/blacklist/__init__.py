import typer

app = typer.Typer()

import museflow.infrastructure.entrypoints.cli.commands.blacklist.add  # noqa: F401,E402
import museflow.infrastructure.entrypoints.cli.commands.blacklist.list_  # noqa: F401,E402
import museflow.infrastructure.entrypoints.cli.commands.blacklist.purge  # noqa: F401,E402
import museflow.infrastructure.entrypoints.cli.commands.blacklist.remove  # noqa: F401,E402
