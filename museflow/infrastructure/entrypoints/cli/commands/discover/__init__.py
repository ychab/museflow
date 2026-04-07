import typer
from rich.console import Console

console = Console()
app = typer.Typer()

import museflow.infrastructure.entrypoints.cli.commands.discover.similar  # noqa: F401,E402
