import asyncio

import typer

from spotifagent.application.services.spotify import TimeRange
from spotifagent.infrastructure.entrypoints.cli.commands.spotify.connect import connect_logic
from spotifagent.infrastructure.entrypoints.cli.commands.spotify.sync_top_items import sync_top_items_logic
from spotifagent.infrastructure.entrypoints.cli.parsers import parse_email

app = typer.Typer()


@app.command("connect", help="Connect a user account to Spotify via OAuth.")
def connect(  # pragma: no cover
    email: str = typer.Option(..., help="User email address", parser=parse_email),
    timeout: float = typer.Option(60.0, help="Seconds to wait for authentication.", min=10),
    poll_interval: float = typer.Option(2.0, help="Seconds between status checks.", min=0.5),
):
    """
    Initiates the Spotify OAuth flow for a specific user.

    Important: the app must be run and being able to receive the Spotify's callback
    define with the setting SPOTIFY_REDIRECT_URI.
    """
    try:
        asyncio.run(connect_logic(email, timeout, poll_interval))
    except Exception as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e


@app.command("sync-top-items", help="Synchronize the Spotify user's top items.")
def sync_top_items(  # pragma: no cover
    email: str = typer.Option(..., help="User email address", parser=parse_email),
    purge_top_artists: bool = typer.Option(
        False,
        "--purge-top-artists/--no-purge-top-artists",
        help="Whether to purge user's top artists",
    ),
    purge_top_tracks: bool = typer.Option(
        False, "--purge-top-tracks/--no-purge-top-tracks", help="Whether to purge user's top tracks"
    ),
    sync_top_artists: bool = typer.Option(
        True,
        "--sync-top-artists/--no-sync-top-artists",
        help="Whether to sync user's top artists",
    ),
    sync_top_tracks: bool = typer.Option(
        True, "--sync-top-tracks/--no-sync-top-tracks", help="Whether to sync user's top tracks"
    ),
    page_limit: int = typer.Option(
        50,
        "--page-limit",
        help="How many top items to fetch per page",
        min=1,
        max=50,
    ),
    time_range: TimeRange = typer.Option(
        "long_term",
        "--time-range",
        help="The time range of the top items to fetch",
    ),
    batch_size: int = typer.Option(
        300,
        "--batch-size",
        help="The number of items to bulk upsert in DB",
        min=1,
        max=500,
    ),
):
    """
    Synchronize the Spotify user's top items into the database, including top artists and top tracks.
    """
    try:
        asyncio.run(
            sync_top_items_logic(
                email=email,
                purge_top_artists=purge_top_artists,
                purge_top_tracks=purge_top_tracks,
                sync_top_artists=sync_top_artists,
                sync_top_tracks=sync_top_tracks,
                page_limit=page_limit,
                time_range=time_range,
                batch_size=batch_size,
            )
        )
    except Exception as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e
