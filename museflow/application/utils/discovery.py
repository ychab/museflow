import logging
from collections import Counter

from museflow.domain.entities.track import Track
from museflow.domain.utils.stats import compute_quality
from museflow.domain.utils.text import normalize_text
from museflow.domain.value_objects.blacklist import UserBlacklist
from museflow.domain.value_objects.stats import ArtistStats
from museflow.domain.value_objects.taste import TrackPicked

logger = logging.getLogger(__name__)


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


def select_tracks(
    tracks_picked: list[TrackPicked],
    max_tracks_per_artist: int,
    playlist_limit: int,
    uncapped_artists: set[str] | None = None,
) -> list[Track]:
    """Returns the playlist tracks: best fit first, capped per credited artist, trimmed to the playlist limit."""
    # A stable sort keeps the advisor's order between equal scores.
    tracks_sorted = sorted(tracks_picked, key=lambda tp: tp.score, reverse=True)
    # Per credited artist: the artists of one scene often feature on each other's tracks.
    tracks = apply_artist_cap(
        tracks=[tp.track for tp in tracks_sorted],
        max_tracks_per_artist=max_tracks_per_artist,
        uncapped_artists=uncapped_artists,
    )
    return tracks[:playlist_limit]


def keep_new_tracks(tracks: list[Track], blacklist: UserBlacklist, fingerprints_seen: set[str]) -> list[Track]:
    """Keeps one track per fingerprint, neither blacklisted nor among `fingerprints_seen` (left unchanged)."""
    kept: list[Track] = []
    fingerprints_kept: set[str] = set()
    for track in tracks:
        if track.fingerprint in fingerprints_seen | fingerprints_kept or _is_blacklisted(track, blacklist):
            continue
        fingerprints_kept.add(track.fingerprint)
        kept.append(track)
    return kept


def _is_blacklisted(track: Track, blacklist: UserBlacklist) -> bool:
    if track.fingerprint in blacklist.track_fingerprints:
        return True
    return bool({normalize_text(a) for a in track.artists} & blacklist.artist_fingerprints)
