import logging
import math
from dataclasses import dataclass
from datetime import UTC
from datetime import datetime

from museflow import __project_name__
from museflow.application.inputs.discovery import DiscoverTasteConfigInput
from museflow.application.ports.advisors.agent import AdvisorAgentPort
from museflow.application.ports.providers.library import ProviderLibraryPort
from museflow.application.ports.repositories.music import TrackRepository
from museflow.application.ports.repositories.taste import TasteProfileRepository
from museflow.application.utils.discovery import TrackScored
from museflow.application.utils.discovery import apply_artist_cap
from museflow.application.utils.discovery import filter_known_tracks
from museflow.application.utils.discovery import reconcile_tracks
from museflow.domain.entities.music import Playlist
from museflow.domain.entities.music import Track
from museflow.domain.entities.music import TrackSuggested
from museflow.domain.entities.user import User
from museflow.domain.exceptions import DiscoveryTrackNoNew
from museflow.domain.exceptions import TasteProfileNotFoundException
from museflow.domain.services.reconciler import TrackReconciler
from museflow.domain.types import TasteProfiler
from museflow.domain.value_objects.taste import DiscoveryTasteStrategy

logger = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class DiscoverTasteAttemptReport:
    attempt: int = 0
    tracks_suggested: int = 0  # after _dedup_by_identity (both reconciled + searched paths)
    tracks_survived: int = 0  # after filter_known_tracks
    tracks_new: int = 0  # after inter-iteration dedup


@dataclass(frozen=True, kw_only=True)
class DiscoverTasteResult:
    playlist: Playlist | None
    strategy: DiscoveryTasteStrategy
    reports: list[DiscoverTasteAttemptReport]
    tracks: list[Track]


class DiscoverTasteUseCase:
    """Use case for discovering new tracks guided by the user's AI taste profile."""

    def __init__(
        self,
        track_repository: TrackRepository,
        taste_profile_repository: TasteProfileRepository,
        provider_library: ProviderLibraryPort,
        advisor_agent: AdvisorAgentPort,
        track_reconciler: TrackReconciler,
        profiler: TasteProfiler,
    ) -> None:
        self._track_repository = track_repository
        self._taste_profile_repository = taste_profile_repository
        self._provider_library = provider_library
        self._advisor_agent = advisor_agent
        self._track_reconciler = track_reconciler
        self._profiler = profiler

    async def create_suggestions_playlist(
        self,
        user: User,
        config: DiscoverTasteConfigInput,
    ) -> DiscoverTasteResult:
        """Creates a playlist of suggested tracks guided by the user's taste profile.

        Iterates up to `max_attempts` times, each time calling the advisor with an exclusion
        list of previously suggested tracks. Stops early once `playlist_size` tracks are
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

        tracks_scores: list[TrackScored] = []
        reports: list[DiscoverTasteAttemptReport] = []
        session_suggestions: list[TrackSuggested] = []
        strategy: DiscoveryTasteStrategy | None = None

        for attempt in range(1, config.max_attempts + 1):
            logger.info(f"### Attempt {attempt}/{config.max_attempts} ###")

            strategy = await self._advisor_agent.get_discovery_strategy(
                profile=profile,
                focus=config.focus,
                similar_limit=config.similar_limit,
                genre=config.genre,
                mood=config.mood,
                custom_instructions=config.custom_instructions,
                excluded_tracks=session_suggestions or None,
            )
            logger.info(
                f"Discovery strategy: '{strategy.strategy_label}'",
                extra={"strategy_label": strategy.strategy_label},
            )

            # Grow the exclusion memory with this attempt's suggestions
            session_suggestions.extend(strategy.recommended_tracks)

            # Reconcile recommended tracks
            tracks_reconciled = await reconcile_tracks(
                tracks_suggested=strategy.recommended_tracks,
                limit=config.candidate_limit,
                provider_library=self._provider_library,
                track_reconciler=self._track_reconciler,
            )
            logger.info(f"Reconciled recommended tracks: {len(tracks_reconciled)}")

            # Search tracks from strategy's queries
            tracks_searched = await self._search_query_tracks(search_queries=strategy.search_queries)
            logger.info(f"Tracks from search queries: {len(tracks_searched)}")

            # Merge and intra-attempt dedup
            tracks_all = self._dedup_by_identity(tracks_reconciled + tracks_searched)

            # Remove known tracks
            tracks_survived = await filter_known_tracks(
                user=user,
                tracks_scored=tracks_all,
                track_repository=self._track_repository,
            )
            logger.info(f"Tracks after filtering known: {len(tracks_survived)}")

            # Inter-iteration dedup: exclude tracks already accumulated in previous attempts
            existing_fps = {ts.track.fingerprint for ts in tracks_scores}
            existing_isrcs = {ts.track.isrc for ts in tracks_scores if ts.track.isrc}
            tracks_new_this_attempt = [
                ts
                for ts in tracks_survived
                if ts.track.fingerprint not in existing_fps
                and (not ts.track.isrc or ts.track.isrc not in existing_isrcs)
            ]

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

            if len(tracks_scores) >= config.playlist_size:
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

        # Trim to the final playlist size
        tracks = tracks[: config.playlist_size]

        if len(tracks) < config.playlist_size:
            logger.warning(
                f"playlist_size not reached ({len(tracks)}/{config.playlist_size}) "
                f"after {config.max_attempts} attempt(s)",
                extra={"found": len(tracks), "target": config.playlist_size},
            )

        if config.dry_run:
            logger.info("Dry-run mode: skipping playlist creation.")
            return DiscoverTasteResult(playlist=None, strategy=strategy, reports=reports, tracks=tracks)

        playlist = await self._provider_library.create_playlist(
            name=f"[{__project_name__.capitalize()}] - {strategy.suggested_playlist_name} - {datetime.now(UTC).isoformat()}",
            tracks=tracks,
        )
        return DiscoverTasteResult(playlist=playlist, strategy=strategy, reports=reports, tracks=tracks)

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
        isrcs: set[str] = set()

        for ts in tracks_scored:
            if ts.track.fingerprint in fingerprints:
                continue
            if ts.track.isrc and ts.track.isrc in isrcs:
                continue

            fingerprints.add(ts.track.fingerprint)
            if ts.track.isrc:
                isrcs.add(ts.track.isrc)

            deduplicated.append(ts)

        return deduplicated
