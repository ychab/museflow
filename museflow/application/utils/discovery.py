import logging
from collections import Counter

from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.domain.entities.track import Track
from museflow.domain.entities.user import User
from museflow.domain.utils.stats import compute_quality
from museflow.domain.utils.text import normalize_text
from museflow.domain.value_objects.stats import ArtistStats

logger = logging.getLogger(__name__)


async def drop_known_tracks(user: User, tracks: list[Track], uow: UnitOfWorkPort) -> list[Track]:
    if not tracks:
        return []
    async with uow:
        known_identifiers = await uow.tracks.get_known_identifiers(
            user_id=user.id,
            fingerprints=[track.fingerprint for track in tracks],
        )

    result: list[Track] = []
    for track in tracks:
        if known_identifiers.is_known(track):
            logger.debug(f"Excluded '{track}'")
            continue
        result.append(track)

    return result


def rank_favourite_artists(all_stats: list[ArtistStats], confidence: int) -> list[str]:
    """Returns the user's favourite artists, best first: ratings first, then plays.

    The artists rated at or above the user's mean come first, by smoothed rating (a Bayesian average: one 10 does not
    beat many 9s), then by plays; then the artists never rated, by plays. An artist rated below the mean is no
    favourite however much played, nor one neither rated nor played.
    """
    rated_count_total = sum(stats.rated_count for stats in all_stats)
    global_mean = sum(stats.rated_sum for stats in all_stats) / rated_count_total if rated_count_total else 0.0

    rated: list[tuple[float, ArtistStats]] = []
    played: list[ArtistStats] = []
    for stats in all_stats:
        if stats.rated_count:
            rate_avg = stats.rated_sum / stats.rated_count
            quality = compute_quality(rate_avg, stats.rated_count, global_mean, confidence)
            if quality >= global_mean:
                rated.append((quality, stats))
        elif stats.plays_count:
            played.append(stats)

    rated.sort(key=lambda item: (-item[0], -item[1].plays_count, item[1].artist))
    played.sort(key=lambda stats: (-stats.plays_count, stats.artist))
    return [stats.artist for _, stats in rated] + [stats.artist for stats in played]


def filter_by_artist(artist: str, tracks: list[Track], log_enabled: bool = True) -> list[Track]:
    """Keeps the tracks crediting `artist`, by exact normalized name: a short name must not match a longer one."""
    target = normalize_text(artist)
    kept = [track for track in tracks if target in {normalize_text(a) for a in track.artists}]

    rejected = {track.primary_artist for track in tracks if track not in kept}
    if rejected and log_enabled:
        logger.debug(f"Artist '{artist}': rejected tracks of {sorted(rejected)}")
    return kept


def apply_artist_cap(
    tracks: list[Track],
    max_tracks_per_artist: int,
    uncapped_artists: set[str] | None = None,
) -> list[Track]:
    """Keeps at most `max_tracks_per_artist` tracks per credited artist: a featured appearance counts too.

    The `uncapped_artists` neither limit a track nor count: a track of theirs is limited by its other artists only.
    """
    tracks_filtered: list[Track] = []
    artist_counts: Counter[str] = Counter()
    uncapped = {normalize_text(a) for a in uncapped_artists or ()}

    for track in tracks:
        artists = {normalize_text(a) for a in track.artists} - uncapped
        if all(artist_counts[artist] < max_tracks_per_artist for artist in artists):
            tracks_filtered.append(track)
            artist_counts.update(artists)

    return tracks_filtered
