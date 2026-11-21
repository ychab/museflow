from typing import Annotated
from typing import cast

import typer

from museflow import __version__
from museflow.infrastructure.config.loggers.setup import configure_loggers
from museflow.infrastructure.config.settings.app import app_settings
from museflow.infrastructure.entrypoints.cli.commands import blacklist
from museflow.infrastructure.entrypoints.cli.commands import enrich
from museflow.infrastructure.entrypoints.cli.commands import llm
from museflow.infrastructure.entrypoints.cli.commands import playlist
from museflow.infrastructure.entrypoints.cli.commands import provider
from museflow.infrastructure.entrypoints.cli.commands import rate
from museflow.infrastructure.entrypoints.cli.commands import stats
from museflow.infrastructure.entrypoints.cli.commands import taste
from museflow.infrastructure.entrypoints.cli.commands import tracks
from museflow.infrastructure.entrypoints.cli.commands import users
from museflow.infrastructure.entrypoints.cli.parsers import parse_log_handlers
from museflow.infrastructure.types import LogHandler
from museflow.infrastructure.types import LogLevel

app = typer.Typer(
    name="Museflow",
    help="CLI for Museflow application.",
    no_args_is_help=True,
)

app.add_typer(blacklist.app, name="blacklist", help="Manage your music blacklist")
app.add_typer(enrich.app, name="enrich", help="Enrich tracks with AI metadata")
app.add_typer(llm.app, name="llm", help="LLM usage and cost commands")
app.add_typer(playlist.app, name="playlist", help="Generate and manage playlists")
app.add_typer(provider.app, name="provider", help="Connect a music provider account")
app.add_typer(rate.app, name="rate", help="Rate a track")
app.add_typer(stats.app, name="stats", help="Stats commands")
app.add_typer(taste.app, name="taste", help="Taste profile commands")
app.add_typer(tracks.app, name="tracks", help="Manage tracks")
app.add_typer(users.app, name="users", help="User management commands")


def version_callback(show_version: bool) -> None:
    if show_version:
        typer.echo(f"Museflow Version: {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    *,
    log_level: Annotated[
        LogLevel, typer.Option("--log-level", "-l", case_sensitive=False, help="Set the logging level.")
    ] = app_settings.LOG_LEVEL_CLI,
    log_handlers: Annotated[
        list[str],
        typer.Option(
            "--log-handlers",
            case_sensitive=True,
            callback=parse_log_handlers,
            help="Set the logging handlers.",
            # A copy: the default must not share the list of the settings.
            default_factory=lambda: list(app_settings.LOG_HANDLERS_CLI),
            show_default=", ".join(app_settings.LOG_HANDLERS_CLI),
        ),
    ],
    version: Annotated[
        bool | None,
        typer.Option(
            "--version",
            "-v",
            help="Show the application's version and exit.",
            callback=version_callback,
            is_eager=True,
        ),
    ] = None,
) -> None:
    """Main entry point for the Museflow CLI application.

    This function initializes the logging configuration.
    """
    configure_loggers(
        level=log_level,
        third_party_level=app_settings.LOG_LEVEL_THIRD_PARTY,
        handlers=cast(list[LogHandler], log_handlers),
    )


# This entrypoint should be used only for local debugging.
if __name__ == "__main__":
    app()
