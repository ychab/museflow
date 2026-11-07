import asyncio
from contextlib import AsyncExitStack
from dataclasses import dataclass

from pydantic import EmailStr

import typer

from museflow.application.ports.providers.library import ProviderLibraryPort
from museflow.application.use_cases.track_rate import TrackRateUseCase
from museflow.domain.enums import MusicProvider
from museflow.domain.enums import TrackSource
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
class RateHistoryResult:
    no_tracks: bool = False
    rated_count: int = 0
    blacklist_track_count: int = 0
    blacklist_artist_count: int = 0
    skipped_count: int = 0


@app.command("history", help="Interactively rate unrated history tracks ordered by play count.")
def rate_history(
    email: str = EMAIL_OPTION,
    limit: int = typer.Option(10, help="Maximum number of tracks to rate", min=1),
    reset: bool = typer.Option(False, "--reset", help="Clear all existing history track scores before rating"),
    play: bool = typer.Option(False, "--play", help="Play each track before rating"),
    play_provider: MusicProvider | None = typer.Option(
        None, "--play-provider", help="Provider to use for playback (default: spotify). Requires --play."
    ),
    artist: str | None = typer.Option(None, "--artist", help="Filter by primary artist (case-insensitive)"),
) -> None:
    if play_provider is not None and not play:
        raise typer.BadParameter("--play-provider requires --play")

    try:
        result = asyncio.run(
            rate_history_logic(
                email=email,
                limit=limit,
                reset=reset,
                provider=(play_provider or MusicProvider.SPOTIFY) if play else None,
                artist=artist,
            )
        )
    except UserNotFound as e:
        raise typer.BadParameter(f"User not found with email: {email}") from e
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
        typer.secho("No unrated history tracks.", fg=typer.colors.YELLOW)
        return

    typer.secho(
        f"\nSaved {result.rated_count} rating(s). "
        f"{result.blacklist_track_count} track(s) and {result.blacklist_artist_count} artist(s) blacklisted. "
        f"{result.skipped_count} track(s) permanently skipped.",
        fg=typer.colors.GREEN,
    )


async def rate_history_logic(
    email: EmailStr,
    limit: int,
    reset: bool,
    provider: MusicProvider | None = None,
    artist: str | None = None,
) -> RateHistoryResult:
    async with AsyncExitStack() as stack:
        uow = get_unit_of_work()

        async with uow:
            user = await uow.users.get_by_email(email)
            if not user:
                raise UserNotFound()

        provider_library: ProviderLibraryPort | None = None
        if provider is not None:
            provider_library = await stack.enter_async_context(get_provider_library(provider, user=user, uow=uow))
        use_case = TrackRateUseCase(user_id=user.id, provider=provider, uow=uow, provider_library=provider_library)

        if reset:
            typer.confirm("This will clear all history track scores. Continue?", abort=True)
            count = await use_case.reset_scores(source=TrackSource.HISTORY)
            typer.secho(f"Reset {count} score(s).", fg=typer.colors.YELLOW)

        tracks = await use_case.find_history(limit=limit, artist=artist)
        if not tracks:
            return RateHistoryResult(no_tracks=True)

        total = len(tracks)
        answers: list[RateAnswer] = []

        for i, track in enumerate(tracks):
            if provider is not None and not await play_track(use_case, track, provider):
                break

            artists_display = ", ".join(track.artists)
            playing_indicator = " ▶ Playing..." if provider is not None else ""
            typer.echo(
                f"\n[{i + 1}/{total}] {artists_display} — {track.name} [played: {track.played_count}x]{playing_indicator}"
            )

            answers.append(await rate_track(use_case, track, allow_permanent_skip=True))

    return RateHistoryResult(
        rated_count=sum(answer.rated for answer in answers),
        blacklist_track_count=sum(answer.track_blacklisted for answer in answers),
        blacklist_artist_count=sum(answer.artist_blacklisted for answer in answers),
        skipped_count=sum(answer.skipped_forever for answer in answers),
    )
