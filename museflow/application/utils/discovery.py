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


def apply_artist_cap(tracks: list[Track], max_tracks_per_artist: int) -> list[Track]:
    """Keeps at most `max_tracks_per_artist` tracks per credited artist: a featured appearance counts too."""
    tracks_filtered: list[Track] = []
    artist_counts: Counter[str] = Counter()

    for track in tracks:
        artists = {normalize_text(a) for a in track.artists}
        if all(artist_counts[artist] < max_tracks_per_artist for artist in artists):
            tracks_filtered.append(track)
            artist_counts.update(artists)

    return tracks_filtered
