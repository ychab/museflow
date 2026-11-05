import typer
from rich.console import Console

console = Console()
app = typer.Typer()


import museflow.infrastructure.entrypoints.cli.commands.provider.connect  # noqa: F401,E402
import museflow.infrastructure.entrypoints.cli.commands.provider.info  # noqa: F401,E402
