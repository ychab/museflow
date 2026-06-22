import asyncio
import uuid
from contextlib import AsyncExitStack
from dataclasses import dataclass

from pydantic import EmailStr

import typer

from museflow.application.ports.providers.library import ProviderLibraryPort
from museflow.application.use_cases.rate import track_rate
from museflow.domain.entities.track import Track
from museflow.domain.exceptions import PlaylistNotFoundError
from museflow.domain.exceptions import ProviderAuthTokenNotFoundError
from museflow.domain.exceptions import ProviderNoActiveDeviceException
from museflow.domain.exceptions import ProviderPremiumRequiredException
from museflow.domain.exceptions import UserNotFound
from museflow.domain.types import DISCOVERY_TRACK_SCORE_MAX
from museflow.domain.types import DISCOVERY_TRACK_SCORE_MIN
from museflow.domain.types import MusicProvider
from museflow.domain.types import SortOrder
from museflow.domain.types import TrackOrderBy
from museflow.domain.types import TrackSource
from museflow.infrastructure.config.settings.app import app_settings
from museflow.infrastructure.entrypoints.cli.commands.rate import app
from museflow.infrastructure.entrypoints.cli.dependencies import get_auth_token_repository
from museflow.infrastructure.entrypoints.cli.dependencies import get_blacklist_repository
from museflow.infrastructure.entrypoints.cli.dependencies import get_db
from museflow.infrastructure.entrypoints.cli.dependencies import get_playlist_repository
from museflow.infrastructure.entrypoints.cli.dependencies import get_provider_library_factory
from museflow.infrastructure.entrypoints.cli.dependencies import get_provider_oauth
from museflow.infrastructure.entrypoints.cli.dependencies import get_track_repository
from museflow.infrastructure.entrypoints.cli.dependencies import get_user_repository
from museflow.infrastructure.entrypoints.cli.parsers import parse_email


@dataclass(frozen=True, kw_only=True)
class RatePlaylistResult:
    no_tracks: bool = False
    rated_count: int = 0
    blacklist_track_count: int = 0
    blacklist_artist_count: int = 0


@app.command(
    "playlist",
    help="Interactively rate tracks in a playlist, or all unrated discovery tracks if no playlist is specified.",
)
def rate_playlist(
    email: str = typer.Option(..., help="User email address", parser=parse_email),
    playlist_id: uuid.UUID | None = typer.Argument(None, help="Playlist UUID to rate"),
    limit: int = typer.Option(20, help="Max unrated tracks to show (queue mode only)"),
    play: bool = typer.Option(False, "--play", help="Play each track before rating"),
    play_provider: MusicProvider = typer.Option(
        MusicProvider.SPOTIFY, "--play-provider", help="Provider to use for playback. Requires --play."
    ),
) -> None:
    try:
        result = asyncio.run(
            rate_playlist_logic(
                email=email,
                playlist_id=playlist_id,
                limit=limit,
                provider=play_provider if play else None,
            )
        )
    except UserNotFound as e:
        raise typer.BadParameter(f"User not found with email: {email}") from e
    except PlaylistNotFoundError as e:
        typer.secho(f"Playlist {playlist_id} not found.", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e
    except ProviderAuthTokenNotFoundError as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e
    except ProviderPremiumRequiredException as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e
    except Exception as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e

    if result.no_tracks:
        typer.secho("No unrated discovery tracks.", fg=typer.colors.YELLOW)
        return

    typer.secho(
        f"\nSaved {result.rated_count} rating(s). "
        f"{result.blacklist_track_count} track(s) and {result.blacklist_artist_count} artist(s) blacklisted.",
        fg=typer.colors.GREEN,
    )


async def rate_playlist_logic(
    email: EmailStr,
    playlist_id: uuid.UUID | None,
    limit: int = 20,
    provider: MusicProvider | None = None,
) -> RatePlaylistResult:
    async with AsyncExitStack() as stack:
        session = await stack.enter_async_context(get_db())

        user_repository = get_user_repository(session)
        playlist_repository = get_playlist_repository(session)
        track_repository = get_track_repository(session)
        blacklist_repository = get_blacklist_repository(session)

        user = await user_repository.get_by_email(email)
        if not user:
            raise UserNotFound()

        provider_library: ProviderLibraryPort | None = None
        if provider is not None:
            provider_client = await stack.enter_async_context(get_provider_oauth(provider))
            auth_token_repository = get_auth_token_repository(session)
            provider_library_factory = get_provider_library_factory(
                provider=provider,
                session=session,
                oauth_client=provider_client,
            )
            auth_token = await auth_token_repository.get(user_id=user.id, provider=provider)
            if auth_token is None:
                raise ProviderAuthTokenNotFoundError(
                    f"No {provider} auth token found — run 'muse {provider} connect' first."
                )
            provider_library = provider_library_factory.create(user=user, auth_token=auth_token)

        tracks: list[Track]
        if playlist_id is not None:
            playlist = await playlist_repository.get(user.id, playlist_id)
            if playlist is None:
                raise PlaylistNotFoundError()
            tracks = playlist.tracks
        else:
            tracks = await track_repository.get_list(
                user_id=user.id,
                source=TrackSource.DISCOVERY,
                unrated_only=True,
                order=[(TrackOrderBy.CREATED_AT, SortOrder.DESC)],
                limit=limit,
            )
            if not tracks:
                return RatePlaylistResult(no_tracks=True)

        threshold = app_settings.DISCOVERY_BLACKLIST_SCORE_THRESHOLD
        total = len(tracks)
        tracks_rated: list[tuple[uuid.UUID, int]] = []
        blacklist_track_pairs: list[tuple[str, str]] = []
        blacklist_artist_names: list[str] = []

        for i, track in enumerate(tracks):
            if provider_library is not None:
                try:
                    await provider_library.play_track(track.provider_id)
                except ProviderNoActiveDeviceException:
                    typer.secho(f"No active {provider} device found.", fg=typer.colors.YELLOW)
                    input("Start playback on your device and press Enter to retry...")
                    try:
                        await provider_library.play_track(track.provider_id)
                    except ProviderNoActiveDeviceException:
                        typer.secho("Device still unavailable — stopping session.", fg=typer.colors.RED, err=True)
                        break

            artists_display = ", ".join(track.artists)
            score_display = f"{track.score}/10" if track.score is not None else "unrated"
            playing_indicator = " ▶ Playing..." if provider is not None else ""
            typer.echo(
                f"\n[{i + 1}/{total}] {artists_display} — {track.name} [current: {score_display}]{playing_indicator}"
            )

            raw = typer.prompt(
                f"  Rate ({DISCOVERY_TRACK_SCORE_MIN}-{DISCOVERY_TRACK_SCORE_MAX}, s=skip)", default="s"
            )
            if raw.strip().lower() == "s":
                continue

            try:
                score_int = int(raw)
            except ValueError:
                typer.secho("  Invalid input, skipping.", fg=typer.colors.YELLOW)
                continue

            if not DISCOVERY_TRACK_SCORE_MIN <= score_int <= DISCOVERY_TRACK_SCORE_MAX:
                typer.secho(
                    f"  Score must be between {DISCOVERY_TRACK_SCORE_MIN} and {DISCOVERY_TRACK_SCORE_MAX}, skipping.",
                    fg=typer.colors.YELLOW,
                )
                continue

            tracks_rated.append((track.id, score_int))

            if score_int <= threshold:
                if typer.confirm("  ↳ Blacklist this track?", default=False):
                    blacklist_track_pairs.append((track.name, track.primary_artist))
                if typer.confirm(f'  ↳ Blacklist artist "{track.primary_artist}"?', default=False):
                    blacklist_artist_names.append(track.primary_artist)

        for track_id, track_score in tracks_rated:
            await track_rate(
                track_id=track_id,
                score=track_score,
                user_id=user.id,
                track_repository=track_repository,
            )

        for track_name, artist_name in blacklist_track_pairs:
            await blacklist_repository.add_track(user_id=user.id, name=track_name, artist_name=artist_name)

        for artist_name in blacklist_artist_names:
            await blacklist_repository.add_artist(user_id=user.id, artist_name=artist_name)

    return RatePlaylistResult(
        rated_count=len(tracks_rated),
        blacklist_track_count=len(blacklist_track_pairs),
        blacklist_artist_count=len(blacklist_artist_names),
    )
