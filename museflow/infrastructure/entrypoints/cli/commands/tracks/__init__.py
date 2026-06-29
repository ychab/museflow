import typer
from rich.console import Console

console = Console()
app = typer.Typer()


import museflow.infrastructure.entrypoints.cli.commands.tracks.delete  # noqa: F401,E402
import museflow.infrastructure.entrypoints.cli.commands.tracks.history  # noqa: F401,E402
