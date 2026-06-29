import typer

app = typer.Typer()

import museflow.infrastructure.entrypoints.cli.commands.enrich.export  # noqa: F401,E402
import museflow.infrastructure.entrypoints.cli.commands.enrich.import_  # noqa: F401,E402
import museflow.infrastructure.entrypoints.cli.commands.enrich.tracks  # noqa: F401,E402
