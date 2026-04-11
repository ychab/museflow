import logging
import math
from collections import Counter
from dataclasses import dataclass
from datetime import UTC
from datetime import datetime

from museflow import __project_name__
from museflow.application.inputs.discovery import DiscoverySimilarConfigInput
from museflow.application.ports.advisors.similar import AdvisorSimilarPort
from museflow.application.ports.providers.library import ProviderLibraryPort
from museflow.application.ports.repositories.music import TrackRepository
from museflow.domain.entities.music import Playlist
from museflow.domain.entities.music import Track
from museflow.domain.entities.music import TrackSuggested
from museflow.domain.entities.user import User
from museflow.domain.exceptions import DiscoveryTrackNoNew
from museflow.domain.exceptions import SimilarTrackResponseException
from museflow.domain.services.reconciler import TrackReconciler
from museflow.domain.types import MusicProvider
from museflow.domain.types import ScoreAdvisor
from museflow.domain.types import ScoreReconciler
from museflow.domain.types import TrackSource

logger = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class DiscoverySimilarAttemptReport:
    attempt: int = 0

    tracks_seeds: int = 0
    tracks_suggested: int = 0
    tracks_reconciled: int = 0
    tracks_survived: int = 0
    tracks_new: int = 0


@dataclass(frozen=True, kw_only=True)
class DiscoverySimilarResult:
    playlist: Playlist | None
    reports: list[DiscoverySimilarAttemptReport]
    tracks: list[Track]


@dataclass(frozen=True, kw_only=True)
class TrackScored:
    track: Track
    advisor_score: ScoreAdvisor
    reconciler_score: ScoreReconciler


class DiscoverSimilarUseCase:
    """Use case for discovering new tracks based on a user's library."""

    def __init__(
        self,
        track_repository: TrackRepository,
        provider_library: ProviderLibraryPort,
        advisor_client: AdvisorSimilarPort,
        track_reconciler: TrackReconciler,
    ) -> None:
        self._track_repository = track_repository
        self._provider_library = provider_library
        self._advisor_client = advisor_client
        self._track_reconciler = track_reconciler

    async def create_suggestions_playlist(
        self,
        user: User,
        config: DiscoverySimilarConfigInput,
    ) -> DiscoverySimilarResult:
        """Creates a playlist of suggested tracks for a user.

        Iterates over seed batches from the user's library until `playlist_size` tracks are
        accumulated or `max_attempts` batches have been processed. The final playlist is trimmed
        to exactly `playlist_size` tracks by the highest advisor score, or shorter if fewer tracks
        were found.

        Args:
            user: The user for whom to create the playlist.
            config: The configuration for the discovery process.

        Returns:
            A DiscoverySimilarResult with the playlist (or ``None`` if dry-run), per-attempt reports,
            and the final list of tracks.

        Raises:
            DiscoveryTrackNoNew: If no new tracks are found after all attempts.
        """
        tracks_scores: list[TrackScored] = []
        reports: list[DiscoverySimilarAttemptReport] = []
        offset = 0

        for attempt in range(1, config.max_attempts + 1):
            logger.info(f"### Attempt {attempt}/{config.max_attempts} ###")

            logger.debug("--- Seed tracks ---")
            track_seeds = await self._track_repository.get_list(
                user_id=user.id,
                provider=MusicProvider.SPOTIFY,
                sources=TrackSource.from_flags(
                    top=config.seed_top,
                    saved=config.seed_saved,
                ),
                genres=config.seed_genres,
                order=[(config.seed_order_by, config.seed_sort_order)],
                limit=config.seed_limit,
                offset=offset,
            )
            if not track_seeds:
                logger.info("Seeds exhausted, stopping.")
                reports.append(DiscoverySimilarAttemptReport(attempt=attempt))
                break

            offset += config.seed_limit
            logger.info(f"Seed tracks: {len(track_seeds)}")

            logger.debug("--- Suggested tracks ---")
            tracks_suggested = await self._get_similar_tracks(track_seeds=track_seeds, limit=config.similar_limit)
            if not tracks_suggested:
                logger.debug(f"Attempt {attempt}: no similar tracks found, continuing...")
                reports.append(
                    DiscoverySimilarAttemptReport(
                        attempt=attempt,
                        tracks_seeds=len(track_seeds),
                    )
                )
                continue
            logger.info(f"Suggested tracks: {len(tracks_suggested)}")

            logger.debug("--- Reconcile suggested tracks ---")
            tracks_reconciled = await self._reconcile_tracks(
                tracks_suggested=tracks_suggested,
                limit=config.candidate_limit,
            )
            if not tracks_reconciled:
                logger.debug(f"Attempt {attempt}: no reconciled tracks found, continuing...")
                reports.append(
                    DiscoverySimilarAttemptReport(
                        attempt=attempt,
                        tracks_seeds=len(track_seeds),
                        tracks_suggested=len(tracks_suggested),
                    )
                )
                continue
            logger.info(f"Reconciled tracks: {len(tracks_reconciled)}")

            logger.debug("--- Deduplicate reconciled tracks ---")
            tracks_survived = await self._deduplicate_tracks(user=user, tracks_reconciled=tracks_reconciled)
            logger.info(f"Survived tracks: {len(tracks_survived)}")

            # Inter-iteration dedup: exclude tracks already accumulated in previous attempts
            existing_fps = {ts.track.fingerprint for ts in tracks_scores}
            existing_isrcs = {ts.track.isrc for ts in tracks_scores if ts.track.isrc}
            tracks_added = [
                ts
                for ts in tracks_survived
                if ts.track.fingerprint not in existing_fps
                and (not ts.track.isrc or ts.track.isrc not in existing_isrcs)
            ]

            reports.append(
                DiscoverySimilarAttemptReport(
                    attempt=attempt,
                    tracks_seeds=len(track_seeds),
                    tracks_suggested=len(tracks_suggested),
                    tracks_reconciled=len(tracks_reconciled),
                    tracks_survived=len(tracks_survived),
                    tracks_new=len(tracks_added),
                )
            )

            tracks_scores.extend(tracks_added)
            logger.info(
                f"=> Attempt {attempt}/{config.max_attempts}: +{len(tracks_added)} tracks (total: {len(tracks_scores)})\n",
                extra={"attempt": attempt, "total": len(tracks_scores)},
            )

            if len(tracks_scores) >= config.playlist_size:
                break

        if not tracks_scores:
            raise DiscoveryTrackNoNew()

        # Sort: band by advisor score DESC, then by reconciler confidence DESC within band
        tracks_scores.sort(
            key=lambda ts: (
                math.floor(ts.advisor_score / config.score_band_width) * config.score_band_width,
                ts.reconciler_score,
            ),
            reverse=True,
        )

        # Apply per-artist cap
        tracks = self._apply_artist_cap(
            tracks=[ts.track for ts in tracks_scores],
            max_tracks_per_artist=config.max_tracks_per_artist,
        )

        # Trim to final playlist size
        tracks = tracks[: config.playlist_size]

        if len(tracks) < config.playlist_size:
            logger.warning(
                f"playlist_size not reached ({len(tracks)}/{config.playlist_size}) "
                f"after {config.max_attempts} attempt(s)",
                extra={"found": len(tracks), "target": config.playlist_size},
            )

        if config.dry_run:
            logger.info("Dry-run mode: skipping playlist creation.")
            return DiscoverySimilarResult(playlist=None, reports=reports, tracks=tracks)

        playlist = await self._provider_library.create_playlist(
            name=f"[{__project_name__.capitalize()}] - {self._advisor_client.display_name} - {datetime.now(UTC).isoformat()}",
            tracks=tracks,
        )
        return DiscoverySimilarResult(playlist=playlist, reports=reports, tracks=tracks)

    async def _get_similar_tracks(self, track_seeds: list[Track], limit: int) -> list[TrackSuggested]:
        """Gets similar tracks from the advisor for a list of seed tracks.

        Args:
            track_seeds: A list of tracks to use as seeds.
            limit: The maximum number of similar tracks to fetch for each seed.

        Returns:
            A list of suggested tracks, sorted by score in descending order.
        """
        tracks_suggested: list[TrackSuggested] = []

        for track_seed in track_seeds:
            try:
                tracks_similar = await self._advisor_client.get_similar_tracks(
                    artist_name=", ".join([a.name for a in track_seed.artists]),
                    track_name=track_seed.name,
                    limit=limit,
                )
            except SimilarTrackResponseException as e:
                logger.exception(f"An error occurred while fetching similar tracks: {e}", extra={"track": track_seed})
                continue

            tracks_suggested.extend(tracks_similar)
            logger.debug(f"Track seed: '{track_seed}' => {len(tracks_similar)} suggestions")

        # Re-order them by score DESC.
        return sorted(tracks_suggested, key=lambda t: t.score, reverse=True)

    async def _reconcile_tracks(self, tracks_suggested: list[TrackSuggested], limit: int) -> list[TrackScored]:
        """Reconciles suggested tracks with the provider.

        Args:
            tracks_suggested: A list of tracks suggested by the advisor.
            limit: The maximum number of search candidates per suggestion.

        Returns:
            A list of reconciled tracks with their advisor and reconciler scores.
        """
        tracks_reconciled: list[TrackScored] = []

        for track_suggested in tracks_suggested:
            candidates = await self._provider_library.search_tracks(
                track=track_suggested.name,
                artists=track_suggested.artists,
                page_size=limit,
                log_enabled=False,
            )

            result = self._track_reconciler.reconcile(
                track_suggested=track_suggested,
                candidates=candidates,
            )
            if result:
                best_match, reconciler_score = result
                tracks_reconciled.append(
                    TrackScored(
                        track=best_match,
                        advisor_score=track_suggested.score,
                        reconciler_score=reconciler_score,
                    )
                )
                logger.debug(f"Track reconciled: '{track_suggested}'")
            else:
                logger.debug(f"Track not reconciled: '{track_suggested}'")

        return tracks_reconciled

    async def _deduplicate_tracks(self, user: User, tracks_reconciled: list[TrackScored]) -> list[TrackScored]:
        """Deduplicate tracks that are already in the user's library.

        Args:
            user: The user to check against.
            tracks_reconciled: A list of scored tracks to filter.

        Returns:
            A list of scored tracks not in the user's library.
        """
        tracks_new: list[TrackScored] = []

        known_identifiers = await self._track_repository.get_known_identifiers(
            user_id=user.id,
            isrcs=[ts.track.isrc for ts in tracks_reconciled if ts.track.isrc],
            fingerprints=[ts.track.fingerprint for ts in tracks_reconciled],
        )

        for ts in tracks_reconciled:
            if known_identifiers.is_known(ts.track):
                logger.debug(f"Excluded '{ts.track}'")
                continue

            tracks_new.append(ts)

        logger.debug(
            f"Discovery:\n- {'\n- '.join([f"'{ts.track}'" for ts in tracks_new])}" if tracks_new else "Discovery: None"
        )
        return tracks_new

    @staticmethod
    def _apply_artist_cap(
        tracks: list[Track],
        max_tracks_per_artist: int,
    ) -> list[Track]:
        tracks_filtered: list[Track] = []

        artist_counts: Counter[str] = Counter()
        for track in tracks:
            artist_provider_id = track.artists[0].provider_id  # Pick only the primary artist.

            if artist_counts[artist_provider_id] < max_tracks_per_artist:
                tracks_filtered.append(track)
                artist_counts[artist_provider_id] += 1

        return tracks_filtered
