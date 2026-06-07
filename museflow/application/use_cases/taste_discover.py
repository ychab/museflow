import logging
import math
import uuid
from dataclasses import dataclass
from dataclasses import replace
from datetime import UTC
from datetime import datetime

from museflow import __project_name__
from museflow.application.inputs.discovery import DiscoverTasteConfigInput
from museflow.application.ports.advisors.agent import AdvisorPort
from museflow.application.ports.providers.library import ProviderLibraryPort
from museflow.application.ports.repositories.blacklist import BlacklistRepository
from museflow.application.ports.repositories.discovery import DiscoveryPlaylistRepository
from museflow.application.ports.repositories.music import TrackRepository
from museflow.application.ports.repositories.taste import TasteProfileRepository
from museflow.application.utils.discovery import TrackScored
from museflow.application.utils.discovery import apply_artist_cap
from museflow.application.utils.discovery import filter_known_tracks
from museflow.application.utils.discovery import reconcile_tracks
from museflow.domain.entities.discovery import DiscoveryPlaylist
from museflow.domain.entities.music import Playlist
from museflow.domain.entities.music import Track
from museflow.domain.entities.music import TrackSuggested
from museflow.domain.entities.taste import TasteProfileStatus
from museflow.domain.entities.user import User
from museflow.domain.exceptions import DiscoveryTrackNoNew
from museflow.domain.exceptions import TasteProfileNotFoundException
from museflow.domain.exceptions import TasteProfileStatusNotReadyException
from museflow.domain.services.reconciler import Reconciler
from museflow.domain.types import TasteProfiler
from museflow.domain.types import TrackSource
from museflow.domain.utils.text import normalize_text
from museflow.domain.value_objects.blacklist import UserBlacklist
from museflow.domain.value_objects.taste import DiscoveryTasteStrategy

logger = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class DiscoverTasteAttemptReport:
    attempt: int = 0
    tracks_suggested: int = 0
    tracks_survived: int = 0
    tracks_new: int = 0


@dataclass(frozen=True, kw_only=True)
class DiscoverTasteResult:
    provider_playlist: Playlist | None
    discovery_playlist: DiscoveryPlaylist | None
    strategy: DiscoveryTasteStrategy
    reports: list[DiscoverTasteAttemptReport]
    tracks: list[Track]


class DiscoverTasteUseCase:
    """Use case for discovering new tracks guided by the user's AI taste profile."""

    def __init__(
        self,
        track_repository: TrackRepository,
        taste_profile_repository: TasteProfileRepository,
        blacklist_repository: BlacklistRepository,
        discovery_playlist_repository: DiscoveryPlaylistRepository,
        provider_library: ProviderLibraryPort,
        advisor: AdvisorPort,
        reconciler: Reconciler,
        profiler: TasteProfiler,
    ) -> None:
        self._track_repository = track_repository
        self._taste_profile_repository = taste_profile_repository
        self._blacklist_repository = blacklist_repository
        self._discovery_playlist_repository = discovery_playlist_repository
        self._provider_library = provider_library
        self._advisor = advisor
        self._reconciler = reconciler
        self._profiler = profiler

    async def create_suggestions_playlist(
        self,
        user: User,
        config: DiscoverTasteConfigInput,
    ) -> DiscoverTasteResult:
        """Creates a playlist of suggested tracks guided by the user's taste profile.

        Iterates up to `max_attempts` times, each time calling the advisor with an exclusion
        list of previously suggested tracks. Stops early once `playlist_limit` tracks are
        accumulated.

        Args:
            user: The user for whom to create the playlist.
            config: The configuration for the discovery process.

        Returns:
            A DiscoverTasteResult with the playlist (or None if dry-run), per-attempt reports,
            the last strategy, and the final list of tracks.

        Raises:
            TasteProfileNotFoundException: If no matching taste profile is found.
            DiscoveryTrackNoNew: If no new tracks are found after all attempts.
        """
        # Load the taste profile once before the loop
        if config.profile_name is not None:
            profile = await self._taste_profile_repository.get(user_id=user.id, name=config.profile_name)
        else:
            profile = await self._taste_profile_repository.get_latest(user_id=user.id, profiler=self._profiler)

        if profile is None:
            raise TasteProfileNotFoundException()
        elif profile.status == TasteProfileStatus.BUILDING:
            raise TasteProfileStatusNotReadyException()

        blacklist = await self._blacklist_repository.get_all_for_user(user.id)
        blacklisted_artists = blacklist.artist_names or None
        blacklisted_tracks = blacklist.track_display_strings or None

        tracks_scores: list[TrackScored] = []
        tracks_suggested: list[TrackSuggested] = []
        reports: list[DiscoverTasteAttemptReport] = []
        strategy: DiscoveryTasteStrategy | None = None

        for attempt in range(1, config.max_attempts + 1):
            logger.info(f"### Attempt {attempt}/{config.max_attempts} ###")

            logger.debug("--- Discovery strategy ---")
            strategy = await self._advisor.get_discovery_strategy(
                profile=profile,
                focus=config.focus,
                advisor_limit=config.advisor_limit,
                genre=config.genre,
                mood=config.mood,
                custom_instructions=config.custom_instructions,
                excluded_tracks=list(tracks_suggested) or None,
                blacklisted_artists=blacklisted_artists,
                blacklisted_tracks=blacklisted_tracks,
            )
            tracks_suggested.extend(strategy.recommended_tracks)
            logger.info(
                f"Discovery strategy: '{strategy.strategy_label}'",
                extra={"strategy_label": strategy.strategy_label},
            )

            # Reconcile recommended tracks
            logger.debug("--- Reconciliation ---")
            tracks_reconciled = await reconcile_tracks(
                tracks_suggested=strategy.recommended_tracks,
                limit=config.reconciler_limit,
                provider_library=self._provider_library,
                reconciler=self._reconciler,
            )
            logger.info(f"Reconciled recommended tracks: {len(tracks_reconciled)}")

            # Search tracks from strategy's queries
            logger.debug("--- Search queries provider ---")
            tracks_searched = await self._search_query_tracks(search_queries=strategy.search_queries)
            logger.info(f"Tracks from search queries: {len(tracks_searched)}")

            # Merge and intra-attempt dedup
            tracks_all = self._dedup_by_identity(tracks_reconciled + tracks_searched)

            # Remove blacklisted artists and tracks (safety net in case the advisor ignored instructions)
            if not blacklist.is_empty:
                tracks_all = [ts for ts in tracks_all if not self._is_blacklisted(ts.track, blacklist)]

            # Remove known tracks
            logger.debug("--- Filter known tracks ---")
            tracks_survived = await filter_known_tracks(
                user=user,
                tracks_scored=tracks_all,
                track_repository=self._track_repository,
            )
            logger.info(f"Tracks after filtering known: {len(tracks_survived)}")

            # Inter-iteration dedup: exclude tracks already accumulated in previous attempts
            existing_fps = {ts.track.fingerprint for ts in tracks_scores}
            tracks_new_this_attempt = [ts for ts in tracks_survived if ts.track.fingerprint not in existing_fps]

            reports.append(
                DiscoverTasteAttemptReport(
                    attempt=attempt,
                    tracks_suggested=len(tracks_all),
                    tracks_survived=len(tracks_survived),
                    tracks_new=len(tracks_new_this_attempt),
                )
            )

            tracks_scores.extend(tracks_new_this_attempt)
            logger.info(
                f"=> Attempt {attempt}/{config.max_attempts}: +{len(tracks_new_this_attempt)} tracks "
                f"(total: {len(tracks_scores)})\n",
                extra={"attempt": attempt, "total": len(tracks_scores)},
            )

            if len(tracks_scores) >= config.playlist_limit:
                break

        if not tracks_scores:
            raise DiscoveryTrackNoNew()

        assert strategy is not None

        # Sort: band by advisor score DESC, then by reconciler confidence DESC within band
        tracks_scores.sort(
            key=lambda ts: (
                math.floor(ts.advisor_score / config.score_band_width) * config.score_band_width,
                ts.reconciler_score,
            ),
            reverse=True,
        )

        # Apply per-artist cap
        tracks = apply_artist_cap(
            tracks=[ts.track for ts in tracks_scores],
            max_tracks_per_artist=config.max_tracks_per_artist,
        )

        # Trim to the final playlist limit
        tracks = tracks[: config.playlist_limit]

        if len(tracks) < config.playlist_limit:
            logger.warning(
                f"playlist_limit not reached ({len(tracks)}/{config.playlist_limit}) "
                f"after {config.max_attempts} attempt(s)",
                extra={"found": len(tracks), "target": config.playlist_limit},
            )

        if config.dry_run:
            logger.info("Dry-run mode: skipping playlist creation.")
            return DiscoverTasteResult(
                provider_playlist=None, discovery_playlist=None, strategy=strategy, reports=reports, tracks=tracks
            )

        # Upsert discovery tracks into museflow_track so they're excluded from future sessions
        discovery_tracks = [
            replace(t, source=TrackSource.DISCOVERY, played_count=0, played_at_first=None, played_at_last=None)
            for t in tracks
        ]
        await self._track_repository.bulk_upsert(discovery_tracks, batch_size=100)
        # Fetch back to get the actual DB UUIDs (needed for the join table FK)
        tracks_db = await self._track_repository.get_list(
            user_id=user.id,
            provider_ids=[t.provider_id for t in discovery_tracks],
        )
        provider_id_to_track = {t.provider_id: t for t in tracks_db}
        tracks_with_ids = [provider_id_to_track[t.provider_id] for t in discovery_tracks]

        playlist = await self._provider_library.create_playlist(
            name=f"[{__project_name__.capitalize()}] - {strategy.suggested_playlist_name} - {datetime.now(UTC).isoformat()}",
            tracks=tracks,
        )

        now = datetime.now(UTC)
        dp = DiscoveryPlaylist(
            id=uuid.uuid4(),
            user_id=user.id,
            profile_id=profile.id,
            provider=playlist.provider,
            provider_id=playlist.provider_id,
            tracks=tracks_with_ids,
            name=strategy.suggested_playlist_name,
            reasoning=strategy.reasoning,
            focus=config.focus,
            genre=config.genre,
            mood=config.mood,
            custom_instructions=config.custom_instructions,
            created_at=now,
            updated_at=now,
        )
        discovery_playlist = await self._discovery_playlist_repository.save(dp)

        return DiscoverTasteResult(
            provider_playlist=playlist,
            discovery_playlist=discovery_playlist,
            strategy=strategy,
            reports=reports,
            tracks=tracks_with_ids,
        )

    @staticmethod
    def _is_blacklisted(track: Track, blacklist: UserBlacklist) -> bool:
        if track.fingerprint in blacklist.track_fingerprints:
            return True
        return bool({normalize_text(a) for a in track.artists} & blacklist.artist_fingerprints)

    async def _search_query_tracks(self, search_queries: list[str]) -> list[TrackScored]:
        tracks_scored: list[TrackScored] = []

        for query in search_queries:
            results = await self._provider_library.search_tracks(
                track=query,
                artists=[],
                page_size=5,
                log_enabled=False,
            )
            tracks_scored.extend(
                TrackScored(track=track, advisor_score=0.8, reconciler_score=1.0) for track in results
            )

        return tracks_scored

    @staticmethod
    def _dedup_by_identity(tracks_scored: list[TrackScored]) -> list[TrackScored]:
        deduplicated: list[TrackScored] = []
        fingerprints: set[str] = set()

        for ts in tracks_scored:
            if ts.track.fingerprint in fingerprints:
                continue
            fingerprints.add(ts.track.fingerprint)
            deduplicated.append(ts)

        return deduplicated
