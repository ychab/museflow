import typer
from rich.console import Console

console = Console()
app = typer.Typer()


import museflow.infrastructure.entrypoints.cli.commands.taste.build  # noqa: F401,E402
