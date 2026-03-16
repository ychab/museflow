import typer
from rich.console import Console

console = Console()
app = typer.Typer()


import museflow.infrastructure.entrypoints.cli.commands.spotify.connect  # noqa: F401,E402
import museflow.infrastructure.entrypoints.cli.commands.spotify.discover  # noqa: F401,E402
import museflow.infrastructure.entrypoints.cli.commands.spotify.info  # noqa: F401,E402
import museflow.infrastructure.entrypoints.cli.commands.spotify.sync  # noqa: F401,E402
