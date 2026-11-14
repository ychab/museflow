import asyncio
import logging
import random
import uuid
from dataclasses import dataclass
from dataclasses import replace
from datetime import UTC
from datetime import datetime
from typing import Final

from museflow.application.inputs.discovery import DiscoverTasteConfigInput
from museflow.application.ports.advisors.agent import AdvisorPort
from museflow.application.ports.providers.library import ProviderLibraryPort
from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.application.services.llm_usage import record_llm_usage
from museflow.application.utils.discovery import apply_artist_cap
from museflow.application.utils.discovery import drop_known_tracks
from museflow.application.utils.discovery import filter_by_artist
from museflow.application.utils.discovery import rank_favourite_artists
from museflow.domain.entities.playlist import Playlist
from museflow.domain.entities.taste import TasteProfile
from museflow.domain.entities.taste import TasteProfileStatus
from museflow.domain.entities.track import Track
from museflow.domain.entities.user import User
from museflow.domain.enums import DiscoveryFocus
from museflow.domain.enums import LLMOperation
from museflow.domain.enums import PlaylistType
from museflow.domain.enums import SortOrder
from museflow.domain.enums import TrackOrderBy
from museflow.domain.enums import TrackSource
from museflow.domain.exceptions import DiscoveryTrackNoNewError
from museflow.domain.exceptions import ProviderSearchQueryInvalidError
from museflow.domain.exceptions import TasteProfileNotFoundError
from museflow.domain.exceptions import TasteProfileStatusNotReadyError
from museflow.domain.utils.text import normalize_text
from museflow.domain.value_objects.blacklist import UserBlacklist
from museflow.domain.value_objects.stats import ArtistStats
from museflow.domain.value_objects.taste import DiscoveryArtistStrategy
from museflow.domain.value_objects.taste import TrackPicked

logger = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class DiscoverTasteAttemptReport:
    attempt: int = 0
    artists: int = 0  # suggested by the advisor
    candidates: int = 0  # their catalogue tracks the user does not know, offered to the advisor
    tracks_picked: int = 0  # among the candidates


@dataclass(frozen=True, kw_only=True)
class DiscoverTasteResult:
    playlist: Playlist | None
    strategy: DiscoveryArtistStrategy | None  # None when the artists come from the user's data, not the advisor
    reports: list[DiscoverTasteAttemptReport]
    tracks: list[Track]


class DiscoverTasteUseCase:
    """Use case for discovering new tracks guided by the user's AI taste profile."""

    # The playlist name without an advisor's suggestion, with the `favourite_artists` focus
    _FAVOURITE_ARTISTS_PLAYLIST_NAME: Final[str] = "Favourite artists"
    # The user's best-rated tracks of a favourite artist shown to the advisor: what they love in them
    _FAVOURITE_ARTIST_LIKED_TRACKS_LIMIT: Final[int] = 5

    def __init__(
        self,
        uow: UnitOfWorkPort,
        provider_library: ProviderLibraryPort,
        advisor: AdvisorPort,
    ) -> None:
        self._uow = uow
        self._provider_library = provider_library
        self._advisor = advisor

    async def create_suggestions_playlist(
        self,
        user: User,
        config: DiscoverTasteConfigInput,
    ) -> DiscoverTasteResult:
        """Creates a playlist of suggested tracks guided by the user's taste profile.

        Each attempt asks the advisor for artists, fetches their catalogue tracks the user does not know, then
        asks the advisor to pick among them, so that no title can be invented. Iterates up to `max_attempts` times,
        each time excluding the artists already asked, and stops once `playlist_limit` tracks are kept after the
        per-artist cap, or once no other artist is wanted: an attempt suggests none, or only artists whose own tracks
        the request asks for. Those are searched deeper and not capped.

        With the `favourite_artists` focus, no advisor call chooses the artists: each attempt takes the next ones
        among the user's favourites (ratings first, then plays), searched deeper but capped, and the run stops once
        none is left.

        Args:
            user: The user for whom to create the playlist.
            config: The configuration for the discovery process.

        Returns:
            A DiscoverTasteResult with the playlist (or None if dry-run), per-attempt reports,
            the last strategy, and the final list of tracks.

        Raises:
            TasteProfileNotFoundError: If no matching taste profile is found.
            DiscoveryTrackNoNewError: If no new tracks are found after all attempts.
        """
        # Load everything the attempts need once, before the loop
        async with self._uow as uow:
            if config.profile_name is not None:
                profile = await uow.taste_profiles.get(user_id=user.id, name=config.profile_name)
            else:
                profile = await uow.taste_profiles.get_latest(user_id=user.id)

            if profile is None:
                raise TasteProfileNotFoundError()
            elif profile.status == TasteProfileStatus.BUILDING:
                raise TasteProfileStatusNotReadyError()

            blacklist = await uow.blacklist.get(user.id)
            liked_tracks = await uow.tracks.get_list(
                user_id=user.id,
                min_score=config.liked_tracks_score_threshold,
                limit=config.liked_tracks_limit,
            )
            disliked_tracks: list[Track] = []
            covered_artists: dict[str, int] = {}
            favourite_artists: list[str] = []
            # The favourites come from the user's data: no artists step, which alone reads the dislikes and coverage.
            if config.focus == DiscoveryFocus.FAVOURITE_ARTISTS:
                artist_stats = await uow.tracks.get_artist_stats(user_id=user.id)
                favourite_artists = self._draw_favourite_artists(artist_stats, blacklist, config)
            else:
                disliked_tracks = await uow.tracks.get_list(
                    user_id=user.id,
                    max_score=config.disliked_tracks_score_threshold,
                    exclude_skipped=True,
                    order=[(TrackOrderBy.SCORE, SortOrder.ASC)],
                    limit=config.disliked_tracks_limit,
                )
                # Told from the first attempt on, so that it suggests fewer known tracks (#154). It mirrors the
                # known-tracks filter, which drops any track of the library: if that filter changes, this count must
                # follow. The most played tracks were measured too: no gain, as 100 tracks barely cover a library of
                # thousands.
                if config.covered_artists_limit > 0:
                    covered_artists = await uow.tracks.get_covered_artists(
                        user_id=user.id, limit=config.covered_artists_limit
                    )

        # What the advisor spent is saved whatever the outcome: a failed discovery was billed too.
        playlist_id: uuid.UUID | None = None
        try:
            result = await self._discover(
                user, config, profile, blacklist, liked_tracks, disliked_tracks, covered_artists, favourite_artists
            )
            playlist_id = result.playlist.id if result.playlist else None
        finally:
            await record_llm_usage(
                user_id=user.id,
                operation=LLMOperation.DISCOVER,
                usages=self._advisor.usages,
                uow=self._uow,
                profile_name=profile.name,
                playlist_id=playlist_id,
            )
        return result

    async def _discover(
        self,
        user: User,
        config: DiscoverTasteConfigInput,
        profile: TasteProfile,
        blacklist: UserBlacklist,
        liked_tracks: list[Track],
        disliked_tracks: list[Track],
        covered_artists: dict[str, int],
        favourite_artists: list[str],
    ) -> DiscoverTasteResult:
        tracks_picked: list[TrackPicked] = []
        # What the playlist would hold now: the loop stops on it, so an attempt cut by the per-artist cap needs another.
        tracks: list[Track] = []
        reports: list[DiscoverTasteAttemptReport] = []
        # Stays None with the `favourite_artists` focus: no advisor call chooses the artists.
        strategy: DiscoveryArtistStrategy | None = None
        # The artists asked in earlier attempts, not to be suggested again.
        artists_asked: list[str] = []
        # The artists whose own tracks the request asks for, kept over the attempts: their tracks stay uncapped.
        artists_requested: set[str] = set()
        from_favourites = config.focus == DiscoveryFocus.FAVOURITE_ARTISTS

        for attempt in range(1, config.max_attempts + 1):
            logger.info(f"### Attempt {attempt}/{config.max_attempts} ###")

            if from_favourites:
                start = (attempt - 1) * config.favourite_artists_per_attempt
                artists = favourite_artists[start : start + config.favourite_artists_per_attempt]
                if not artists:
                    logger.info(f"Attempt {attempt}/{config.max_attempts}: no favourite artist left, stopping")
                    break
                # Their best-known tracks are the user's already: the catalogue search reaches the others.
                artists_deep = set(artists)
                for artist_name in artists:
                    logger.debug(f"Favourite artist '{artist_name}'")
                logger.info(f"Favourite artists: {len(artists)}", extra={"artists": len(artists)})
            else:
                logger.debug("--- Discovery artists ---")
                strategy_now = await self._advisor.get_discovery_artists(
                    profile=profile,
                    artists_limit=config.advisor_limit,
                    prompt=config.prompt,
                    focus=config.focus,
                    excluded_artists=list(artists_asked) or None,
                    blacklisted_artists=blacklist.artist_names or None,
                    blacklisted_tracks=blacklist.track_display_strings or None,
                    liked_tracks=liked_tracks,
                    disliked_tracks=disliked_tracks,
                    covered_artists=covered_artists or None,
                )
                # No artist left: a request naming only artists already got them, another attempt would be paid for
                # nothing. The previous strategy is kept, as it chose the tracks.
                if not strategy_now.artists and strategy is not None:
                    logger.info(f"Attempt {attempt}/{config.max_attempts}: no artist left to suggest, stopping")
                    break
                strategy = strategy_now

                artists = [artist.name for artist in strategy.artists]
                artists_deep = {artist.name for artist in strategy.artists if artist.requested}
                artists_asked.extend(artists)
                artists_requested.update(artists_deep)
                for artist in strategy.artists:
                    requested = " [requested]" if artist.requested else ""
                    logger.debug(f"Artist suggested '{artist.name}'{requested} ({artist.score:.2f}): {artist.sound}")
                logger.info(
                    f"Discovery strategy: '{strategy.strategy_label}' ({len(strategy.artists)} artists)",
                    extra={"strategy_label": strategy.strategy_label, "artists": len(strategy.artists)},
                )

            candidates = await self._get_candidates(
                user=user,
                config=config,
                artists=artists,
                artists_deep=artists_deep,
                blacklist=blacklist,
                fingerprints_kept={tp.track.fingerprint for tp in tracks_picked},
            )

            tracks_picked_now: list[TrackPicked] = []
            if candidates:
                logger.debug("--- Picks ---")
                tracks_picked_now = await self._advisor.pick_discovery_tracks(
                    strategy=strategy,
                    candidates=candidates,
                    tracks_limit=config.advisor_limit,
                    max_tracks_per_artist=config.max_tracks_per_artist,
                    prompt=config.prompt,
                    focus=config.focus,
                    liked_tracks=self._group_liked_tracks(liked_tracks, artists=list(candidates))
                    if from_favourites
                    else None,
                )
                for track_picked in tracks_picked_now:
                    logger.debug(f"Picked ({track_picked.score:.2f}): '{track_picked.track}'")

            reports.append(
                DiscoverTasteAttemptReport(
                    attempt=attempt,
                    artists=len(artists),
                    candidates=sum(len(tracks) for tracks in candidates.values()),
                    tracks_picked=len(tracks_picked_now),
                )
            )

            tracks_picked.extend(tracks_picked_now)
            tracks = self._select_tracks(
                tracks_picked=tracks_picked,
                artists_requested=artists_requested,
                config=config,
            )
            logger.info(
                f"=> Attempt {attempt}/{config.max_attempts}: +{len(tracks_picked_now)} tracks "
                f"(total: {len(tracks_picked)}, {len(tracks)} kept)\n",
                extra={"attempt": attempt, "total": len(tracks_picked), "kept": len(tracks)},
            )

            if len(tracks) >= config.playlist_limit:
                break
            # Only artists the request asks for: it names no other, and theirs were searched as deep as configured.
            if strategy is not None and all(artist.requested for artist in strategy.artists):
                logger.info(f"Attempt {attempt}/{config.max_attempts}: only requested artists, stopping")
                break

        if not tracks:
            raise DiscoveryTrackNoNewError()

        if len(tracks) < config.playlist_limit:
            logger.warning(
                f"playlist_limit not reached ({len(tracks)}/{config.playlist_limit}) after {len(reports)} attempt(s)",
                extra={"found": len(tracks), "target": config.playlist_limit, "attempts": len(reports)},
            )

        if config.dry_run:
            logger.info("Dry-run mode: skipping playlist creation.")
            return DiscoverTasteResult(playlist=None, strategy=strategy, reports=reports, tracks=tracks)

        suggested_name = strategy.suggested_playlist_name if strategy else self._FAVOURITE_ARTISTS_PLAYLIST_NAME
        name = config.title or f"[MF] - {suggested_name} - {datetime.now(UTC).isoformat(timespec='seconds')}"
        # Remote first: if the provider call fails, nothing has been written locally.
        playlist = await self._provider_library.create_playlist(
            name=name,
            type=PlaylistType.DISCOVERY,
            tracks=tracks,
        )

        # Upsert discovery tracks into museflow_track so they're excluded from future sessions
        discovery_tracks = [replace(t, source=TrackSource.DISCOVERY) for t in tracks]
        # One block: the discovery tracks and their local playlist are saved together, or not at all.
        async with self._uow as uow:
            track_ids, _ = await uow.tracks.bulk_upsert(discovery_tracks, batch_size=100)
            # The DB IDs are needed for the join table FK (an existing row keeps its own ID).
            tracks_with_ids = [replace(t, id=track_ids[t.fingerprint]) for t in discovery_tracks]

            playlist = replace(
                playlist,
                profile_id=profile.id,
                reasoning=strategy.reasoning if strategy else None,
                prompt=config.prompt,
                focus=config.focus,
                tracks=tracks_with_ids,
            )
            playlist_db = await uow.playlists.create(playlist)

        return DiscoverTasteResult(
            playlist=playlist_db,
            strategy=strategy,
            reports=reports,
            tracks=tracks_with_ids,
        )

    async def _get_candidates(
        self,
        user: User,
        config: DiscoverTasteConfigInput,
        artists: list[str],
        artists_deep: set[str],
        blacklist: UserBlacklist,
        fingerprints_kept: set[str],
    ) -> dict[str, list[Track]]:
        """Returns the catalogue tracks of each artist the user does not know, per artist name.

        The `artists_deep` get the catalogue search, deeper than the plain one. A track is kept only when it credits
        the artist, and is neither blacklisted nor kept by an earlier attempt.
        """
        logger.debug("--- Artist tracks ---")
        # Searched concurrently, a few at a time not to hit the rate limit; gather keeps the artists' order, so the
        # first artist still keeps a track two of them share.
        semaphore = asyncio.Semaphore(config.artist_tracks_concurrency)
        searches = [
            asyncio.create_task(
                self._search_artist_tracks(
                    artist=artist,
                    deep=artist in artists_deep,
                    config=config,
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
            kept: list[Track] = []
            for track in tracks_matched:
                if track.fingerprint in fingerprints_seen or self._is_blacklisted(track, blacklist):
                    continue
                fingerprints_seen.add(track.fingerprint)
                kept.append(track)
            logger.debug(f"Artist '{artist}': {len(tracks)} found, {len(tracks_matched)} matched")
            if kept:
                candidates[artist] = kept

        # Known tracks dropped locally: the advisor never sees them, so it cannot pick them.
        tracks_unknown = await drop_known_tracks(
            user=user,
            tracks=[track for tracks in candidates.values() for track in tracks],
            uow=self._uow,
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

    async def _search_artist_tracks(
        self,
        artist: str,
        deep: bool,
        config: DiscoverTasteConfigInput,
        semaphore: asyncio.Semaphore,
    ) -> list[Track] | None:
        """Returns the catalogue tracks found for the artist, or None if the provider rejected its search query."""
        async with semaphore:
            try:
                # The search ranks by popularity: for an artist the request asks for, or a favourite one, the first
                # results are their best-known tracks, likely known to the user already.
                if deep:
                    return await self._provider_library.search_artist_catalogue(
                        artist=artist,
                        max_pages=config.requested_artist_tracks_pages,
                    )
                return await self._provider_library.search_artist_tracks(
                    artist=artist,
                    max_pages=config.artist_tracks_pages,
                    log_enabled=False,
                )
            except ProviderSearchQueryInvalidError:
                # One malformed name must not end the run: the other artists, and the advisor call paid, are kept.
                logger.warning(f"Artist skipped, its search query was rejected: '{artist}'")
                return None

    @staticmethod
    def _select_tracks(
        tracks_picked: list[TrackPicked],
        artists_requested: set[str],
        config: DiscoverTasteConfigInput,
    ) -> list[Track]:
        """Returns the playlist tracks: best fit first, capped per credited artist, trimmed to the playlist limit."""
        # A stable sort keeps the advisor's order between equal scores.
        tracks_sorted = sorted(tracks_picked, key=lambda tp: tp.score, reverse=True)
        # Per credited artist: the suggested artists often feature on each other's tracks. The artists the request
        # asks for are the playlist itself: no cap.
        tracks = apply_artist_cap(
            tracks=[tp.track for tp in tracks_sorted],
            max_tracks_per_artist=config.max_tracks_per_artist,
            uncapped_artists=artists_requested,
        )
        return tracks[: config.playlist_limit]

    @staticmethod
    def _draw_favourite_artists(
        artist_stats: list[ArtistStats],
        blacklist: UserBlacklist,
        config: DiscoverTasteConfigInput,
    ) -> list[str]:
        """Returns the user's best favourite artists, not blacklisted, in a random order.

        Shuffled so that two runs start with other artists: the attempts take them in this order.
        """
        favourite_artists = [
            artist
            for artist in rank_favourite_artists(artist_stats, confidence=config.favourite_artists_confidence)
            if normalize_text(artist) not in blacklist.artist_fingerprints
        ][: config.favourite_artists_limit]
        random.shuffle(favourite_artists)
        logger.info(
            f"Favourite artists drawn: {len(favourite_artists)}",
            extra={"favourite_artists": len(favourite_artists)},
        )
        return favourite_artists

    @classmethod
    def _group_liked_tracks(cls, liked_tracks: list[Track], artists: list[str]) -> dict[str, list[Track]]:
        """Returns the user's best-rated tracks crediting each artist, best first, for the artists with any."""
        liked_by_artist: dict[str, list[Track]] = {}
        for artist in artists:
            liked = filter_by_artist(artist=artist, tracks=liked_tracks, log_enabled=False)
            if liked:
                liked_by_artist[artist] = liked[: cls._FAVOURITE_ARTIST_LIKED_TRACKS_LIMIT]
        return liked_by_artist

    @staticmethod
    def _is_blacklisted(track: Track, blacklist: UserBlacklist) -> bool:
        if track.fingerprint in blacklist.track_fingerprints:
            return True
        return bool({normalize_text(a) for a in track.artists} & blacklist.artist_fingerprints)
