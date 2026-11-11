import typer
from rich.console import Console

app = typer.Typer()
console = Console()

import museflow.infrastructure.entrypoints.cli.commands.stats.artists  # noqa: F401,E402
import museflow.infrastructure.entrypoints.cli.commands.stats.candidates  # noqa: F401,E402
import museflow.infrastructure.entrypoints.cli.commands.stats.tags  # noqa: F401,E402
import museflow.infrastructure.entrypoints.cli.commands.stats.tracks  # noqa: F401,E402
