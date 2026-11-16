import asyncio
import logging
import uuid
from dataclasses import replace

from museflow.application.ports.providers.library import ProviderLibraryPort
from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.application.utils.discovery import drop_tracks_known_by_credits
from museflow.application.utils.discovery import filter_by_artist
from museflow.application.utils.discovery import is_live_or_medley
from museflow.application.utils.discovery import keep_new_tracks
from museflow.domain.entities.playlist import Playlist
from museflow.domain.entities.track import Track
from museflow.domain.entities.user import User
from museflow.domain.enums import DiscoveryFocus
from museflow.domain.enums import PlaylistType
from museflow.domain.enums import TrackSource
from museflow.domain.exceptions import ProviderSearchQueryInvalidError
from museflow.domain.utils.text import get_fingerprint_title
from museflow.domain.value_objects.blacklist import UserBlacklist

logger = logging.getLogger(__name__)


class DiscoveryService:
    """The steps shared by the use cases building a playlist from artists' catalogues: `discover` and `explore`."""

    def __init__(self, uow: UnitOfWorkPort, provider_library: ProviderLibraryPort) -> None:
        self._uow = uow
        self._provider_library = provider_library

    async def get_unknown_artist_tracks(
        self,
        user: User,
        artists: list[str],
        artists_deep: set[str],
        blacklist: UserBlacklist,
        fingerprints_kept: set[str],
        artist_tracks_pages: int,
        catalogue_tracks_pages: int,
        concurrency: int,
    ) -> dict[str, list[Track]]:
        """Returns the catalogue tracks of each artist the user does not know, per artist name, for the advisor.

        The `artists_deep` get the catalogue search, `catalogue_tracks_pages` per query; the others the plain search,
        `artist_tracks_pages` deep. A track is kept only when it credits the artist, and is neither blacklisted nor in
        `fingerprints_kept` (kept by an earlier round); an artist left with no track is left out. The `artists_deep`
        are the ones whose original tracks are wanted: their live recordings and medleys are left out too.
        """
        # Searched concurrently, a few at a time not to hit the rate limit; gather keeps the artists' order, so the
        # first artist still keeps a track two of them share.
        semaphore = asyncio.Semaphore(concurrency)
        searches = [
            asyncio.create_task(
                self._search_artist_tracks(
                    artist=artist,
                    max_pages=catalogue_tracks_pages if artist in artists_deep else artist_tracks_pages,
                    deep=artist in artists_deep,
                    semaphore=semaphore,
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
            if artist in artists_deep:
                tracks_matched = [track for track in tracks_matched if not is_live_or_medley(track)]
            kept = keep_new_tracks(tracks=tracks_matched, blacklist=blacklist, fingerprints_seen=fingerprints_seen)
            fingerprints_seen.update(track.fingerprint for track in kept)
            logger.debug(f"Artist '{artist}': {len(tracks)} found, {len(tracks_matched)} matched")
            if kept:
                candidates[artist] = kept

        # Known tracks dropped locally: the advisor never sees them, so it cannot pick them.
        tracks_unknown = await self._drop_known_tracks(
            user=user,
            tracks=[track for tracks in candidates.values() for track in tracks],
        )
        fingerprints_unknown = {track.fingerprint for track in tracks_unknown}
        candidates = {
            artist: unknown
            for artist, tracks in candidates.items()
            if (unknown := [track for track in tracks if track.fingerprint in fingerprints_unknown])
        }
        logger.debug(
            f"Artist tracks: {found} found, {matched} by the artist, {len(tracks_unknown)} unknown "
            f"({len(candidates)}/{len(artists)} artists left)",
            extra={"found": found, "matched": matched, "unknown": len(tracks_unknown), "artists": len(candidates)},
        )
        return candidates

    async def create_playlist(
        self,
        *,
        name: str,
        type: PlaylistType,
        tracks: list[Track],
        profile_id: uuid.UUID | None = None,
        reasoning: str | None = None,
        prompt: str | None = None,
        focus: DiscoveryFocus | None = None,
    ) -> Playlist:
        """Creates the playlist on the provider, then saves it with its tracks, as discoveries the next runs exclude."""
        # Remote first: if the provider call fails, nothing has been written locally.
        playlist = await self._provider_library.create_playlist(name=name, type=type, tracks=tracks)

        discovery_tracks = [replace(track, source=TrackSource.DISCOVERY) for track in tracks]
        # One block: the discovery tracks and their local playlist are saved together, or not at all.
        async with self._uow as uow:
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
        self,
        artist: str,
        max_pages: int,
        deep: bool,
        semaphore: asyncio.Semaphore,
    ) -> list[Track] | None:
        """Returns the catalogue tracks found for the artist, or None if the provider rejected its search query."""
        async with semaphore:
            try:
                # The search ranks by popularity: for an artist searched deep, the first results are their best-known
                # tracks, likely known to the user already.
                if deep:
                    return await self._provider_library.search_artist_catalogue(artist=artist, max_pages=max_pages)
                return await self._provider_library.search_artist_tracks(artist=artist, max_pages=max_pages)
            except ProviderSearchQueryInvalidError:
                # One malformed name must not end the run: the other artists, and the advisor call paid, are kept.
                logger.warning(f"Artist skipped, its search query was rejected: '{artist}'")
                return None

    async def _drop_known_tracks(self, user: User, tracks: list[Track]) -> list[Track]:
        if not tracks:
            return []
        library_tracks: list[Track] = []

        async with self._uow as uow:
            known_identifiers = await uow.tracks.get_known_identifiers(
                user_id=user.id,
                fingerprints=[track.fingerprint for track in tracks],
            )
            tracks_unknown: list[Track] = []
            for track in tracks:
                if known_identifiers.is_known(track):
                    logger.debug(f"Excluded '{track}'")
                    continue
                tracks_unknown.append(track)

            # The fingerprint holds the first artist only: the same song credited in another order is caught by its
            # title, among the tracks the fingerprint let through only.
            if tracks_unknown:
                library_tracks = await uow.tracks.get_list(
                    user_id=user.id,
                    titles=sorted({get_fingerprint_title(track.fingerprint) for track in tracks_unknown}),
                )

        return drop_tracks_known_by_credits(tracks=tracks_unknown, library_tracks=library_tracks)
