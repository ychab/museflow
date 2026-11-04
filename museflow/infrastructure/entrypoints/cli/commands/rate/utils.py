from dataclasses import dataclass

import typer

from museflow.application.use_cases.track_rate import TrackRateUseCase
from museflow.domain.const import DISCOVERY_TRACK_SCORE_MAX
from museflow.domain.const import DISCOVERY_TRACK_SCORE_MIN
from museflow.domain.entities.track import Track
from museflow.domain.enums import MusicProvider
from museflow.domain.exceptions import ProviderNoActiveDeviceException
from museflow.infrastructure.config.settings.app import app_settings


@dataclass(frozen=True, kw_only=True)
class RateAnswer:
    rated: bool = False
    skipped_forever: bool = False
    track_blacklisted: bool = False
    artist_blacklisted: bool = False


async def play_track(use_case: TrackRateUseCase, track: Track, provider: MusicProvider) -> bool:
    """Plays the track, asking once to start a device; returns False when there is still none."""
    try:
        await use_case.play(track)
    except ProviderNoActiveDeviceException:
        typer.secho(f"No active {provider} device found.", fg=typer.colors.YELLOW)
        input("Start playback on your device and press Enter to retry...")
        try:
            await use_case.play(track)
        except ProviderNoActiveDeviceException:
            typer.secho("Device still unavailable — stopping session.", fg=typer.colors.RED, err=True)
            return False

    return True


async def rate_track(use_case: TrackRateUseCase, track: Track, allow_permanent_skip: bool) -> RateAnswer:
    """Prompts until a valid answer, saves it, then offers the blacklist for a low score."""
    choices = "s=skip, u=permanently skip" if allow_permanent_skip else "s=skip"
    while True:
        raw = typer.prompt(f"  Rate ({DISCOVERY_TRACK_SCORE_MIN}-{DISCOVERY_TRACK_SCORE_MAX}, {choices})", default="s")
        answer = raw.strip().lower()
        if answer == "s":
            return RateAnswer()
        if allow_permanent_skip and answer == "u":
            await use_case.skip(track_id=track.id)
            return RateAnswer(skipped_forever=True)

        try:
            score = int(answer)
        except ValueError:
            typer.secho("  Invalid input, try again.", fg=typer.colors.YELLOW)
            continue

        if DISCOVERY_TRACK_SCORE_MIN <= score <= DISCOVERY_TRACK_SCORE_MAX:
            break

        typer.secho(
            f"  Score must be between {DISCOVERY_TRACK_SCORE_MIN} and {DISCOVERY_TRACK_SCORE_MAX}, try again.",
            fg=typer.colors.YELLOW,
        )

    await use_case.rate(track_id=track.id, score=score)

    track_blacklisted = False
    artist_blacklisted = False
    if score <= app_settings.DISCOVERY_BLACKLIST_SCORE_THRESHOLD:
        if typer.confirm("  ↳ Blacklist this track?", default=False):
            await use_case.blacklist_track(name=track.name, artist_name=track.primary_artist)
            track_blacklisted = True
        if typer.confirm(f'  ↳ Blacklist artist "{track.primary_artist}"?', default=False):
            await use_case.blacklist_artist(artist_name=track.primary_artist)
            artist_blacklisted = True

    return RateAnswer(rated=True, track_blacklisted=track_blacklisted, artist_blacklisted=artist_blacklisted)
