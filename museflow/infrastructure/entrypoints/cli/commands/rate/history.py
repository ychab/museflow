from contextlib import AsyncExitStack
from dataclasses import dataclass

from pydantic import EmailStr

import typer

from museflow.application.ports.providers.library import ProviderLibraryPort
from museflow.application.use_cases.track_rate import RateTrackUseCase
from museflow.application.use_cases.user_get import get_user
from museflow.domain.enums import MusicProvider
from museflow.domain.enums import TrackSource
from museflow.domain.exceptions import ProviderAuthTokenNotFoundError
from museflow.domain.exceptions import ProviderPremiumRequiredError
from museflow.domain.exceptions import UserNotFoundError
from museflow.infrastructure.entrypoints.cli.commands.rate import app
from museflow.infrastructure.entrypoints.cli.commands.rate.utils import RateAnswer
from museflow.infrastructure.entrypoints.cli.commands.rate.utils import play_track
from museflow.infrastructure.entrypoints.cli.commands.rate.utils import rate_track
from museflow.infrastructure.entrypoints.cli.dependencies import get_unit_of_work
from museflow.infrastructure.entrypoints.cli.dependencies import init_logic_runner
from museflow.infrastructure.entrypoints.cli.options import EMAIL_OPTION
from museflow.infrastructure.entrypoints.wiring import build_provider_library


@dataclass(frozen=True, kw_only=True)
class RateHistoryResult:
    no_tracks: bool = False
    rated_count: int = 0
    blacklist_track_count: int = 0
    blacklist_artist_count: int = 0
    skipped_count: int = 0


@app.command("history", help="Interactively rate unrated history tracks ordered by play count.")
def rate_history_command(
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

    if reset:
        typer.confirm("This will clear all history track scores. Continue?", abort=True)

    try:
        # One runner for both steps: the reset count prints before the rating loop starts.
        with init_logic_runner() as runner:
            if reset:
                count = runner.run(rate_history_reset_logic(email=email))
                typer.secho(f"Reset {count} score(s).", fg=typer.colors.YELLOW)

            result = runner.run(
                rate_history_logic(
                    email=email,
                    limit=limit,
                    provider=(play_provider or MusicProvider.SPOTIFY) if play else None,
                    artist=artist,
                )
            )
    except UserNotFoundError as e:
        raise typer.BadParameter(f"User not found with email: {email}") from e
    except ProviderAuthTokenNotFoundError as e:
        typer.secho(f"Error: {e} Run 'museflow provider connect' first.", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e
    except ProviderPremiumRequiredError as e:
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


async def rate_history_reset_logic(email: EmailStr) -> int:
    uow = get_unit_of_work()

    user = await get_user(email=email, uow=uow)

    use_case = RateTrackUseCase(user_id=user.id, provider=None, uow=uow)
    return await use_case.reset_scores(source=TrackSource.HISTORY)


async def rate_history_logic(
    email: EmailStr,
    limit: int,
    provider: MusicProvider | None = None,
    artist: str | None = None,
) -> RateHistoryResult:
    async with AsyncExitStack() as stack:
        uow = get_unit_of_work()

        user = await get_user(email=email, uow=uow)

        provider_library: ProviderLibraryPort | None = None
        if provider is not None:
            provider_library = await stack.enter_async_context(
                build_provider_library(provider, user=user, uow=uow, token_uow=get_unit_of_work())
            )
        use_case = RateTrackUseCase(user_id=user.id, provider=provider, uow=uow, provider_library=provider_library)

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
