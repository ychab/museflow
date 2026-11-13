import logging
from collections import Counter

from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.domain.entities.track import Track
from museflow.domain.entities.user import User
from museflow.domain.utils.text import normalize_text

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


def filter_by_artist(artist: str, tracks: list[Track]) -> list[Track]:
    """Keeps the tracks crediting `artist`, by exact normalized name: a short name must not match a longer one."""
    target = normalize_text(artist)
    kept = [track for track in tracks if target in {normalize_text(a) for a in track.artists}]

    rejected = {track.primary_artist for track in tracks if track not in kept}
    if rejected:
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
