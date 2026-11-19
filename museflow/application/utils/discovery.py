import logging
import re
from collections import Counter
from typing import Final

from museflow.domain.entities.track import Track
from museflow.domain.utils.stats import compute_quality
from museflow.domain.utils.text import get_fingerprint_title
from museflow.domain.utils.text import normalize_text
from museflow.domain.utils.text import unidecode_lower_text
from museflow.domain.value_objects.blacklist import UserBlacklist
from museflow.domain.value_objects.stats import ArtistStats
from museflow.domain.value_objects.taste import TrackPicked

logger = logging.getLogger(__name__)

# A live recording: a version tag after a dash or in brackets, or "live at/from/in"; a bare "live" is a word of the
# title too ("Live Your Life")
_LIVE_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"([-(\[]\s*(live|en vivo|ao vivo|en directo|en concierto|en concert)\b)|\blive (at|from|in)\b"
)
_MEDLEY_PATTERN: Final[re.Pattern[str]] = re.compile(r"\b(medley|popurri)\b")
# The artists whose tracks filter_by_artist rejects, named in its log at most
_REJECTED_LOGGED_MAX: Final[int] = 10


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

    rejected = sorted({track.primary_artist for track in tracks if track not in kept})
    if rejected and log_enabled:
        # A short name matches hundreds of others in the catalogue: their first ones are enough to see why
        more = len(rejected) - _REJECTED_LOGGED_MAX
        listed = f"{rejected[:_REJECTED_LOGGED_MAX]} (+{more} more)" if more > 0 else f"{rejected}"
        logger.debug(f"Artist {artist!r}: rejected tracks of {listed}")

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


def is_live_or_medley(track: Track) -> bool:
    """True for a live recording, by its title or album, or a medley: neither is a track a fan missed.

    A medley is named so, or chains three titles or more with " / ".
    """
    name = unidecode_lower_text(track.name)
    album = unidecode_lower_text(track.album_name or "")
    if _LIVE_PATTERN.search(name) or _LIVE_PATTERN.search(album):
        return True
    return bool(_MEDLEY_PATTERN.search(name)) or name.count(" / ") >= 2


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


def drop_tracks_known_by_credits(tracks: list[Track], library_tracks: list[Track]) -> list[Track]:
    """Drops the tracks the library holds under the same normalized title with at least one credited artist in common.

    Catches what the fingerprint (title + first artist) misses: the same song credited in another order.
    """
    # Accepted risk (#214): two different songs with one title and one artist in common (an "Intro" on two albums)
    # count as one, as the fingerprint already does when that artist is credited first.
    library_artists: dict[str, set[str]] = {}

    for library_track in library_tracks:
        title = get_fingerprint_title(library_track.fingerprint)
        library_artists.setdefault(title, set()).update(normalize_text(a) for a in library_track.artists)

    kept: list[Track] = []

    for track in tracks:
        artists = library_artists.get(get_fingerprint_title(track.fingerprint), set())
        if artists & {normalize_text(a) for a in track.artists}:
            logger.debug(f"Excluded {str(track)!r}: known under other credits")
            continue

        kept.append(track)

    return kept


def _is_blacklisted(track: Track, blacklist: UserBlacklist) -> bool:
    if track.fingerprint in blacklist.track_fingerprints:
        return True
    return bool({normalize_text(a) for a in track.artists} & blacklist.artist_fingerprints)
