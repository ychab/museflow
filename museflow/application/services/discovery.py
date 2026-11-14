import asyncio
import logging
import uuid
from dataclasses import replace

from museflow.application.ports.providers.library import ProviderLibraryPort
from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.application.utils.discovery import filter_by_artist
from museflow.application.utils.discovery import is_blacklisted
from museflow.domain.entities.playlist import Playlist
from museflow.domain.entities.track import Track
from museflow.domain.entities.user import User
from museflow.domain.enums import DiscoveryFocus
from museflow.domain.enums import PlaylistType
from museflow.domain.enums import TrackSource
from museflow.domain.exceptions import ProviderSearchQueryInvalidError
from museflow.domain.value_objects.blacklist import UserBlacklist

logger = logging.getLogger(__name__)


async def get_unknown_artist_tracks(
    user: User,
    artists: list[str],
    artists_deep: set[str],
    blacklist: UserBlacklist,
    fingerprints_kept: set[str],
    artist_tracks_pages: int,
    catalogue_tracks_pages: int,
    concurrency: int,
    uow: UnitOfWorkPort,
    provider_library: ProviderLibraryPort,
) -> dict[str, list[Track]]:
    """Returns the catalogue tracks of each artist the user does not know, per artist name, for the advisor to pick.

    The `artists_deep` get the catalogue search, `catalogue_tracks_pages` per query; the others the plain search,
    `artist_tracks_pages` deep. A track is kept only when it credits the artist, and is neither blacklisted nor in
    `fingerprints_kept` (kept by an earlier round); an artist left with no track is left out.
    """
    logger.debug("--- Artist tracks ---")
    # Searched concurrently, a few at a time not to hit the rate limit; gather keeps the artists' order, so the first
    # artist still keeps a track two of them share.
    semaphore = asyncio.Semaphore(concurrency)
    searches = [
        asyncio.create_task(
            _search_artist_tracks(
                artist=artist,
                max_pages=catalogue_tracks_pages if artist in artists_deep else artist_tracks_pages,
                deep=artist in artists_deep,
                semaphore=semaphore,
                provider_library=provider_library,
            )
        )
        for artist in artists
    ]
    try:
        results = await asyncio.gather(*searches)
    finally:
        # A failed search leaves the others running: cancel them (a no-op on those already done).
        for search in searches:
            search.cancel()

    candidates: dict[str, list[Track]] = {}
    fingerprints_seen = set(fingerprints_kept)
    found = matched = 0
    for artist, tracks in zip(artists, results, strict=True):
        if tracks is None:
            continue

        tracks_matched = filter_by_artist(artist=artist, tracks=tracks)
        found += len(tracks)
        matched += len(tracks_matched)
        kept: list[Track] = []
        for track in tracks_matched:
            if track.fingerprint in fingerprints_seen or is_blacklisted(track, blacklist):
                continue
            fingerprints_seen.add(track.fingerprint)
            kept.append(track)
        logger.debug(f"Artist '{artist}': {len(tracks)} found, {len(tracks_matched)} matched")
        if kept:
            candidates[artist] = kept

    # Known tracks dropped locally: the advisor never sees them, so it cannot pick them.
    tracks_unknown = await _drop_known_tracks(
        user=user,
        tracks=[track for tracks in candidates.values() for track in tracks],
        uow=uow,
    )
    fingerprints_unknown = {track.fingerprint for track in tracks_unknown}
    candidates = {
        artist: unknown
        for artist, tracks in candidates.items()
        if (unknown := [track for track in tracks if track.fingerprint in fingerprints_unknown])
    }
    logger.info(
        f"Artist tracks: {found} found, {matched} by the artist, {len(tracks_unknown)} unknown "
        f"({len(candidates)}/{len(artists)} artists left)",
        extra={"found": found, "matched": matched, "unknown": len(tracks_unknown), "artists": len(candidates)},
    )
    return candidates


async def create_discovery_playlist(
    *,
    name: str,
    tracks: list[Track],
    profile_id: uuid.UUID | None = None,
    reasoning: str | None = None,
    prompt: str | None = None,
    focus: DiscoveryFocus | None = None,
    uow: UnitOfWorkPort,
    provider_library: ProviderLibraryPort,
) -> Playlist:
    """Creates the playlist on the provider, then saves it with its tracks, as discoveries the next runs exclude.

    Typed `discovery` for `playlist explore` too, until it gets a type of its own (#209).
    """
    # Remote first: if the provider call fails, nothing has been written locally.
    playlist = await provider_library.create_playlist(name=name, type=PlaylistType.DISCOVERY, tracks=tracks)

    discovery_tracks = [replace(track, source=TrackSource.DISCOVERY) for track in tracks]
    # One block: the discovery tracks and their local playlist are saved together, or not at all.
    async with uow:
        track_ids, _ = await uow.tracks.bulk_upsert(discovery_tracks, batch_size=100)
        # The DB IDs are needed for the join table FK (an existing row keeps its own ID).
        tracks_with_ids = [replace(track, id=track_ids[track.fingerprint]) for track in discovery_tracks]

        playlist = replace(
            playlist,
            profile_id=profile_id,
            reasoning=reasoning,
            prompt=prompt,
            focus=focus,
            tracks=tracks_with_ids,
        )
        return await uow.playlists.create(playlist)


async def _search_artist_tracks(
    artist: str,
    max_pages: int,
    deep: bool,
    semaphore: asyncio.Semaphore,
    provider_library: ProviderLibraryPort,
) -> list[Track] | None:
    """Returns the catalogue tracks found for the artist, or None if the provider rejected its search query."""
    async with semaphore:
        try:
            # The search ranks by popularity: for an artist searched deep, the first results are their best-known
            # tracks, likely known to the user already.
            if deep:
                return await provider_library.search_artist_catalogue(artist=artist, max_pages=max_pages)
            return await provider_library.search_artist_tracks(artist=artist, max_pages=max_pages, log_enabled=False)
        except ProviderSearchQueryInvalidError:
            # One malformed name must not end the run: the other artists, and the advisor call paid, are kept.
            logger.warning(f"Artist skipped, its search query was rejected: '{artist}'")
            return None


async def _drop_known_tracks(user: User, tracks: list[Track], uow: UnitOfWorkPort) -> list[Track]:
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
