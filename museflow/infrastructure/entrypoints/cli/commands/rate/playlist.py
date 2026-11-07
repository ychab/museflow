import asyncio
import uuid
from contextlib import AsyncExitStack
from dataclasses import dataclass

from pydantic import EmailStr

import typer

from museflow.application.ports.providers.library import ProviderLibraryPort
from museflow.application.use_cases.track_rate import RateTrackUseCase
from museflow.domain.enums import MusicProvider
from museflow.domain.exceptions import PlaylistNotFoundError
from museflow.domain.exceptions import ProviderAuthTokenNotFoundError
from museflow.domain.exceptions import ProviderPremiumRequiredException
from museflow.domain.exceptions import UserNotFound
from museflow.infrastructure.entrypoints.cli.commands.rate import app
from museflow.infrastructure.entrypoints.cli.commands.rate.utils import RateAnswer
from museflow.infrastructure.entrypoints.cli.commands.rate.utils import play_track
from museflow.infrastructure.entrypoints.cli.commands.rate.utils import rate_track
from museflow.infrastructure.entrypoints.cli.dependencies import get_provider_library
from museflow.infrastructure.entrypoints.cli.dependencies import get_unit_of_work
from museflow.infrastructure.entrypoints.cli.options import EMAIL_OPTION


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
def rate_playlist_command(
    email: str = EMAIL_OPTION,
    playlist_id: uuid.UUID | None = typer.Argument(None, help="Playlist UUID to rate"),
    limit: int = typer.Option(20, help="Max unrated tracks to show (queue mode only)", min=1),
    play: bool = typer.Option(False, "--play", help="Play each track before rating"),
    play_provider: MusicProvider | None = typer.Option(
        None, "--play-provider", help="Provider to use for playback (default: spotify). Requires --play."
    ),
) -> None:
    if play_provider is not None and not play:
        raise typer.BadParameter("--play-provider requires --play")

    try:
        result = asyncio.run(
            rate_playlist_logic(
                email=email,
                playlist_id=playlist_id,
                limit=limit,
                provider=(play_provider or MusicProvider.SPOTIFY) if play else None,
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
        message = f"Playlist {playlist_id} has no tracks." if playlist_id else "No unrated discovery tracks."
        typer.secho(message, fg=typer.colors.YELLOW)
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
        uow = get_unit_of_work()

        async with uow:
            user = await uow.users.get_by_email(email)
            if not user:
                raise UserNotFound()

        provider_library: ProviderLibraryPort | None = None
        if provider is not None:
            provider_library = await stack.enter_async_context(get_provider_library(provider, user=user, uow=uow))
        use_case = RateTrackUseCase(user_id=user.id, provider=provider, uow=uow, provider_library=provider_library)

        if playlist_id is not None:
            tracks = await use_case.find_playlist(playlist_id=playlist_id)
        else:
            tracks = await use_case.find_discovery(limit=limit)

        if not tracks:
            return RatePlaylistResult(no_tracks=True)

        total = len(tracks)
        answers: list[RateAnswer] = []

        for i, track in enumerate(tracks):
            if provider is not None and not await play_track(use_case, track, provider):
                break

            artists_display = ", ".join(track.artists)
            score_display = f"{track.score}/10" if track.score is not None else "unrated"
            playing_indicator = " ▶ Playing..." if provider is not None else ""
            typer.echo(
                f"\n[{i + 1}/{total}] {artists_display} — {track.name} [current: {score_display}]{playing_indicator}"
            )

            answers.append(await rate_track(use_case, track, allow_permanent_skip=False))

    return RatePlaylistResult(
        rated_count=sum(answer.rated for answer in answers),
        blacklist_track_count=sum(answer.track_blacklisted for answer in answers),
        blacklist_artist_count=sum(answer.artist_blacklisted for answer in answers),
    )
