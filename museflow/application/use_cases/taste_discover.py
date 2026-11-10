import logging
import uuid
from dataclasses import dataclass
from dataclasses import replace
from datetime import UTC
from datetime import datetime

from museflow.application.inputs.discovery import DiscoverTasteConfigInput
from museflow.application.ports.advisors.agent import AdvisorPort
from museflow.application.ports.providers.library import ProviderLibraryPort
from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.application.services.llm_usage import record_llm_usage
from museflow.application.utils.discovery import apply_artist_cap
from museflow.application.utils.discovery import drop_known_tracks
from museflow.application.utils.discovery import filter_by_artist
from museflow.domain.entities.playlist import Playlist
from museflow.domain.entities.taste import TasteProfile
from museflow.domain.entities.taste import TasteProfileStatus
from museflow.domain.entities.track import Track
from museflow.domain.entities.user import User
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
    strategy: DiscoveryArtistStrategy
    reports: list[DiscoverTasteAttemptReport]
    tracks: list[Track]


class DiscoverTasteUseCase:
    """Use case for discovering new tracks guided by the user's AI taste profile."""

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
        per-artist cap.

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
            covered_artists: dict[str, int] = {}
            if config.covered_artists_limit > 0:
                covered_artists = await uow.tracks.get_covered_artists(
                    user_id=user.id, limit=config.covered_artists_limit
                )

        # What the advisor spent is saved whatever the outcome: a failed discovery was billed too.
        playlist_id: uuid.UUID | None = None
        try:
            result = await self._discover(
                user, config, profile, blacklist, liked_tracks, disliked_tracks, covered_artists
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
    ) -> DiscoverTasteResult:
        tracks_picked: list[TrackPicked] = []
        # What the playlist would hold now: the loop stops on it, so an attempt cut by the per-artist cap needs another.
        tracks: list[Track] = []
        reports: list[DiscoverTasteAttemptReport] = []
        strategy: DiscoveryArtistStrategy | None = None
        # The artists asked in earlier attempts, not to be suggested again.
        artists_asked: list[str] = []

        for attempt in range(1, config.max_attempts + 1):
            logger.info(f"### Attempt {attempt}/{config.max_attempts} ###")

            logger.debug("--- Discovery artists ---")
            strategy = await self._advisor.get_discovery_artists(
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
            artists_asked.extend(artist.name for artist in strategy.artists)
            for artist in strategy.artists:
                logger.debug(f"Artist suggested '{artist.name}' ({artist.score:.2f}): {artist.sound}")
            logger.info(
                f"Discovery strategy: '{strategy.strategy_label}' ({len(strategy.artists)} artists)",
                extra={"strategy_label": strategy.strategy_label, "artists": len(strategy.artists)},
            )

            candidates = await self._get_candidates(
                user=user,
                config=config,
                strategy=strategy,
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
                )
                for track_picked in tracks_picked_now:
                    logger.debug(f"Picked ({track_picked.score:.2f}): '{track_picked.track}'")

            reports.append(
                DiscoverTasteAttemptReport(
                    attempt=attempt,
                    artists=len(strategy.artists),
                    candidates=sum(len(tracks) for tracks in candidates.values()),
                    tracks_picked=len(tracks_picked_now),
                )
            )

            tracks_picked.extend(tracks_picked_now)
            tracks = self._select_tracks(tracks_picked=tracks_picked, config=config)
            logger.info(
                f"=> Attempt {attempt}/{config.max_attempts}: +{len(tracks_picked_now)} tracks "
                f"(total: {len(tracks_picked)}, {len(tracks)} kept)\n",
                extra={"attempt": attempt, "total": len(tracks_picked), "kept": len(tracks)},
            )

            if len(tracks) >= config.playlist_limit:
                break

        # strategy can only be None if no attempt ran, which DiscoverTasteConfigInput forbids (max_attempts >= 1)
        if strategy is None or not tracks:
            raise DiscoveryTrackNoNewError()

        if len(tracks) < config.playlist_limit:
            logger.warning(
                f"playlist_limit not reached ({len(tracks)}/{config.playlist_limit}) after {len(reports)} attempt(s)",
                extra={"found": len(tracks), "target": config.playlist_limit, "attempts": len(reports)},
            )

        if config.dry_run:
            logger.info("Dry-run mode: skipping playlist creation.")
            return DiscoverTasteResult(playlist=None, strategy=strategy, reports=reports, tracks=tracks)

        # Remote first: if the provider call fails, nothing has been written locally.
        playlist = await self._provider_library.create_playlist(
            name=f"[MF] - {strategy.suggested_playlist_name} - {datetime.now(UTC).isoformat(timespec='seconds')}",
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
                reasoning=strategy.reasoning,
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
        strategy: DiscoveryArtistStrategy,
        blacklist: UserBlacklist,
        fingerprints_kept: set[str],
    ) -> dict[str, list[Track]]:
        """Returns the catalogue tracks of each suggested artist the user does not know, per artist name.

        A track is kept only when it credits the artist, and is neither blacklisted nor kept by an earlier attempt.
        """
        logger.debug("--- Artist tracks ---")
        candidates: dict[str, list[Track]] = {}
        fingerprints_seen = set(fingerprints_kept)
        found = matched = 0
        for artist in strategy.artists:
            try:
                tracks = await self._provider_library.search_artist_tracks(
                    artist=artist.name,
                    max_pages=config.artist_tracks_pages,
                    log_enabled=False,
                )
            except ProviderSearchQueryInvalidError:
                # One malformed name must not end the run: the other artists, and the advisor call paid, are kept.
                logger.warning(f"Artist skipped, its search query was rejected: '{artist.name}'")
                continue

            tracks_matched = filter_by_artist(artist=artist.name, tracks=tracks)
            found += len(tracks)
            matched += len(tracks_matched)
            kept: list[Track] = []
            for track in tracks_matched:
                if track.fingerprint in fingerprints_seen or self._is_blacklisted(track, blacklist):
                    continue
                fingerprints_seen.add(track.fingerprint)
                kept.append(track)
            logger.debug(f"Artist '{artist.name}': {len(tracks)} found, {len(tracks_matched)} matched")
            if kept:
                candidates[artist.name] = kept

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
            f"({len(candidates)}/{len(strategy.artists)} artists left)",
            extra={"found": found, "matched": matched, "unknown": len(tracks_unknown), "artists": len(candidates)},
        )
        return candidates

    @staticmethod
    def _select_tracks(tracks_picked: list[TrackPicked], config: DiscoverTasteConfigInput) -> list[Track]:
        """Returns the playlist tracks: best fit first, capped per credited artist, trimmed to the playlist limit."""
        # A stable sort keeps the advisor's order between equal scores.
        tracks_sorted = sorted(tracks_picked, key=lambda tp: tp.score, reverse=True)
        # Per credited artist: the suggested artists often feature on each other's tracks.
        tracks = apply_artist_cap(
            tracks=[tp.track for tp in tracks_sorted],
            max_tracks_per_artist=config.max_tracks_per_artist,
        )
        return tracks[: config.playlist_limit]

    @staticmethod
    def _is_blacklisted(track: Track, blacklist: UserBlacklist) -> bool:
        if track.fingerprint in blacklist.track_fingerprints:
            return True
        return bool({normalize_text(a) for a in track.artists} & blacklist.artist_fingerprints)
