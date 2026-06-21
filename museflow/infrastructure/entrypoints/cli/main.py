from typing import cast

import typer

from museflow import __version__
from museflow.infrastructure.config.loggers import configure_loggers
from museflow.infrastructure.config.settings.app import app_settings
from museflow.infrastructure.entrypoints.cli.commands import blacklist
from museflow.infrastructure.entrypoints.cli.commands import playlist
from museflow.infrastructure.entrypoints.cli.commands import rate
from museflow.infrastructure.entrypoints.cli.commands import spotify
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
app.add_typer(playlist.app, name="playlist", help="Generate and manage playlists")
app.add_typer(rate.app, name="rate", help="Rate a track")
app.add_typer(spotify.app, name="spotify", help="Spotify interaction commands")
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
    log_level: LogLevel = typer.Option(
        app_settings.LOG_LEVEL_CLI,
        "--log-level",
        "-l",
        case_sensitive=False,
        help="Set the logging level.",
    ),
    log_handlers: list[str] = typer.Option(
        app_settings.LOG_HANDLERS_CLI,
        "--log-handlers",
        case_sensitive=True,
        callback=parse_log_handlers,
        help="Set the logging handlers.",
    ),
    version: bool | None = typer.Option(
        None,
        "--version",
        "-v",
        help="Show the application's version and exit.",
        callback=version_callback,
        is_eager=True,
    ),
):
    """Main entry point for the Museflow CLI application.

    This function initializes the logging configuration.
    """
    configure_loggers(level=log_level, handlers=cast(list[LogHandler], log_handlers))


# This entrypoint should be used only for local debugging.
if __name__ == "__main__":
    app()
