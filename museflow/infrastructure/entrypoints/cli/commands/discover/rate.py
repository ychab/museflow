import asyncio
import uuid
from contextlib import AsyncExitStack

import typer
from rich.console import Console

from museflow.application.inputs.discovery import BlacklistChoiceInput
from museflow.application.inputs.discovery import DiscoveryPlaylistRatingInput
from museflow.application.use_cases.discovery_playlist_rate import discovery_playlist_rate
from museflow.application.use_cases.discovery_playlist_view import discovery_playlist_view
from museflow.domain.exceptions import DiscoveryPlaylistNotFoundError
from museflow.domain.exceptions import UserNotFound
from museflow.domain.types import DISCOVERY_TRACK_SCORE_MAX
from museflow.domain.types import DISCOVERY_TRACK_SCORE_MIN
from museflow.infrastructure.config.settings.app import app_settings
from museflow.infrastructure.entrypoints.cli.commands.discover import app
from museflow.infrastructure.entrypoints.cli.dependencies import get_blacklist_repository
from museflow.infrastructure.entrypoints.cli.dependencies import get_db
from museflow.infrastructure.entrypoints.cli.dependencies import get_discovery_playlist_repository
from museflow.infrastructure.entrypoints.cli.dependencies import get_user_repository
from museflow.infrastructure.entrypoints.cli.parsers import parse_email

console = Console()


@app.command("rate")
def rate(
    playlist_id: uuid.UUID = typer.Argument(..., help="Discovery playlist ID"),
    email: str = typer.Option(..., help="User email address", parser=parse_email),
) -> None:
    """Interactively rate tracks in a discovery playlist."""
    try:
        asyncio.run(rate_logic(email=email, playlist_id=playlist_id))
    except UserNotFound as e:
        raise typer.BadParameter(f"User not found with email: {email}") from e
    except DiscoveryPlaylistNotFoundError as e:
        typer.secho(f"Playlist {playlist_id} not found.", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e
    except Exception as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e


async def rate_logic(email: str, playlist_id: uuid.UUID) -> None:
    async with AsyncExitStack() as stack:
        session = await stack.enter_async_context(get_db())

        user_repository = get_user_repository(session)
        discovery_playlist_repository = get_discovery_playlist_repository(session)
        blacklist_repository = get_blacklist_repository(session)

        user = await user_repository.get_by_email(email)
        if not user:
            raise UserNotFound()

        playlist = await discovery_playlist_view(
            user=user,
            playlist_id=playlist_id,
            discovery_playlist_repository=discovery_playlist_repository,
        )

        ratings: list[DiscoveryPlaylistRatingInput] = []
        blacklist_choices: list[BlacklistChoiceInput] = []
        threshold = app_settings.DISCOVERY_BLACKLIST_SCORE_THRESHOLD

        total = len(playlist.tracks)
        for track in playlist.tracks:
            artists_display = ", ".join(track.artist_names)
            typer.echo(f"\n[{track.position + 1}/{total}] {artists_display} — {track.track_name}")

            raw = typer.prompt(
                f"  Rate ({DISCOVERY_TRACK_SCORE_MIN}-{DISCOVERY_TRACK_SCORE_MAX}, s=skip)", default="s"
            )
            if raw.strip().lower() == "s":
                continue

            try:
                score = int(raw)
                if not DISCOVERY_TRACK_SCORE_MIN <= score <= DISCOVERY_TRACK_SCORE_MAX:
                    typer.secho(
                        f"  Score must be between {DISCOVERY_TRACK_SCORE_MIN} and {DISCOVERY_TRACK_SCORE_MAX}, skipping.",
                        fg=typer.colors.YELLOW,
                    )
                    continue
            except ValueError:
                typer.secho("  Invalid input, skipping.", fg=typer.colors.YELLOW)
                continue

            ratings.append(DiscoveryPlaylistRatingInput(track_id=track.id, score=score))

            if score <= threshold:
                primary_artist = track.artist_names[0]
                blacklist_track = typer.confirm("  ↳ Blacklist this track?", default=False)
                blacklist_artist = typer.confirm(f'  ↳ Blacklist artist "{primary_artist}"?', default=False)
                if blacklist_track or blacklist_artist:
                    blacklist_choices.append(
                        BlacklistChoiceInput(
                            track_name=track.track_name,
                            artist_name=primary_artist,
                            blacklist_track=blacklist_track,
                            blacklist_artist=blacklist_artist,
                        )
                    )

        await discovery_playlist_rate(
            user=user,
            ratings=ratings,
            blacklist_choices=blacklist_choices,
            discovery_playlist_repository=discovery_playlist_repository,
            blacklist_repository=blacklist_repository,
        )

    tracks_blacklisted = sum(1 for c in blacklist_choices if c.blacklist_track)
    artists_blacklisted = sum(1 for c in blacklist_choices if c.blacklist_artist)
    typer.secho(
        f"\nSaved {len(ratings)} rating(s). "
        f"{tracks_blacklisted} track(s) and {artists_blacklisted} artist(s) blacklisted.",
        fg=typer.colors.GREEN,
    )
