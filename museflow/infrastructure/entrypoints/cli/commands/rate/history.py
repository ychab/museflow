import asyncio
from contextlib import AsyncExitStack
from dataclasses import dataclass

from pydantic import EmailStr

import typer

from museflow.application.ports.providers.library import ProviderLibraryPort
from museflow.application.use_cases.track_rate import TrackRateUseCase
from museflow.domain.const import DISCOVERY_TRACK_SCORE_MAX
from museflow.domain.const import DISCOVERY_TRACK_SCORE_MIN
from museflow.domain.enums import MusicProvider
from museflow.domain.enums import TrackSource
from museflow.domain.exceptions import ProviderAuthTokenNotFoundError
from museflow.domain.exceptions import ProviderNoActiveDeviceException
from museflow.domain.exceptions import ProviderPremiumRequiredException
from museflow.domain.exceptions import UserNotFound
from museflow.infrastructure.config.settings.app import app_settings
from museflow.infrastructure.entrypoints.cli.commands.rate import app
from museflow.infrastructure.entrypoints.cli.dependencies import get_provider_library
from museflow.infrastructure.entrypoints.cli.dependencies import get_unit_of_work
from museflow.infrastructure.entrypoints.cli.parsers import parse_email


@dataclass(frozen=True, kw_only=True)
class RateHistoryResult:
    no_tracks: bool = False
    rated_count: int = 0
    blacklist_track_count: int = 0
    blacklist_artist_count: int = 0
    skipped_count: int = 0


@app.command("history", help="Interactively rate unrated history tracks ordered by play count.")
def rate_history(
    email: str = typer.Option(..., help="User email address", parser=parse_email),
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

        threshold = app_settings.DISCOVERY_BLACKLIST_SCORE_THRESHOLD
        total = len(tracks)
        rated_count = 0
        skipped_count = 0
        blacklist_track_count = 0
        blacklist_artist_count = 0

        for i, track in enumerate(tracks):
            if provider is not None:
                try:
                    await use_case.play(track)
                except ProviderNoActiveDeviceException:
                    typer.secho(f"No active {provider} device found.", fg=typer.colors.YELLOW)
                    input("Start playback on your device and press Enter to retry...")
                    try:
                        await use_case.play(track)
                    except ProviderNoActiveDeviceException:
                        typer.secho("Device still unavailable — stopping session.", fg=typer.colors.RED, err=True)
                        break

            artists_display = ", ".join(track.artists)
            playing_indicator = " ▶ Playing..." if provider is not None else ""
            typer.echo(
                f"\n[{i + 1}/{total}] {artists_display} — {track.name} [played: {track.played_count}x]{playing_indicator}"
            )

            while True:
                raw = typer.prompt(
                    f"  Rate ({DISCOVERY_TRACK_SCORE_MIN}-{DISCOVERY_TRACK_SCORE_MAX}, s=skip, u=permanently skip)",
                    default="s",
                )
                if raw.strip().lower() == "s":
                    break
                if raw.strip().lower() == "u":
                    await use_case.skip(track_id=track.id)
                    skipped_count += 1
                    break

                try:
                    score_int = int(raw)
                except ValueError:
                    typer.secho("  Invalid input, try again.", fg=typer.colors.YELLOW)
                    continue

                if not DISCOVERY_TRACK_SCORE_MIN <= score_int <= DISCOVERY_TRACK_SCORE_MAX:
                    typer.secho(
                        f"  Score must be between {DISCOVERY_TRACK_SCORE_MIN} and {DISCOVERY_TRACK_SCORE_MAX}, try again.",
                        fg=typer.colors.YELLOW,
                    )
                    continue

                await use_case.rate(track_id=track.id, score=score_int)
                rated_count += 1

                if score_int <= threshold:
                    if typer.confirm("  ↳ Blacklist this track?", default=False):
                        await use_case.blacklist_track(name=track.name, artist_name=track.primary_artist)
                        blacklist_track_count += 1
                    if typer.confirm(f'  ↳ Blacklist artist "{track.primary_artist}"?', default=False):
                        await use_case.blacklist_artist(artist_name=track.primary_artist)
                        blacklist_artist_count += 1
                break

    return RateHistoryResult(
        rated_count=rated_count,
        blacklist_track_count=blacklist_track_count,
        blacklist_artist_count=blacklist_artist_count,
        skipped_count=skipped_count,
    )
