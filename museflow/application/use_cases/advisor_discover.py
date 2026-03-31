import logging
from dataclasses import dataclass
from datetime import UTC
from datetime import datetime

from museflow import __project_name__
from museflow.application.inputs.discovery import DiscoveryConfigInput
from museflow.application.ports.advisors.client import AdvisorClientPort
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
from museflow.domain.types import Score
from museflow.domain.types import TrackSource

logger = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class DiscoveryAttemptReport:
    attempt: int = 0

    tracks_seeds: int = 0
    tracks_suggested: int = 0
    tracks_reconciled: int = 0
    tracks_survived: int = 0
    tracks_new: int = 0


@dataclass(frozen=True, kw_only=True)
class DiscoveryResult:
    playlist: Playlist | None
    reports: list[DiscoveryAttemptReport]
    tracks: list[Track]


class AdvisorDiscoverUseCase:
    """Use case for discovering new tracks based on a user's library."""

    def __init__(
        self,
        track_repository: TrackRepository,
        provider_library: ProviderLibraryPort,
        advisor_client: AdvisorClientPort,
        track_reconciler: TrackReconciler,
    ) -> None:
        self._track_repository = track_repository
        self._provider_library = provider_library
        self._advisor_client = advisor_client
        self._track_reconciler = track_reconciler

    async def create_suggestions_playlist(self, user: User, config: DiscoveryConfigInput) -> DiscoveryResult:
        """Creates a playlist of suggested tracks for a user.

        Iterates over seed batches from the user's library until `playlist_size` tracks are
        accumulated or `max_attempts` batches have been processed. The final playlist is trimmed
        to exactly `playlist_size` tracks by the highest advisor score, or shorter if fewer tracks
        were found.

        Args:
            user: The user for whom to create the playlist.
            config: The configuration for the discovery process.

        Returns:
            A DiscoveryResult with the playlist (or ``None`` if dry-run), per-attempt reports,
            and the final list of tracks.

        Raises:
            DiscoveryTrackNoNew: If no new tracks are found after all attempts.
        """
        tracks_scores: list[tuple[Track, Score]] = []
        reports: list[DiscoveryAttemptReport] = []
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
                order_by=config.seed_order_by,
                sort_order=config.seed_sort_order,
                limit=config.seed_limit,
                offset=offset,
            )
            if not track_seeds:
                logger.info("Seeds exhausted, stopping.")
                reports.append(DiscoveryAttemptReport(attempt=attempt))
                break

            offset += config.seed_limit
            logger.info(f"Seed tracks: {len(track_seeds)}")

            logger.debug("--- Suggested tracks ---")
            tracks_suggested = await self._get_similar_tracks(track_seeds=track_seeds, limit=config.similar_limit)
            if not tracks_suggested:
                logger.debug(f"Attempt {attempt}: no similar tracks found, continuing...")
                reports.append(DiscoveryAttemptReport(attempt=attempt, tracks_seeds=len(track_seeds)))
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
                    DiscoveryAttemptReport(
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
            existing_fps = {t.fingerprint for t, _ in tracks_scores}
            existing_isrcs = {t.isrc for t, _ in tracks_scores if t.isrc}
            tracks_added = [
                (t, s)
                for t, s in tracks_survived
                if t.fingerprint not in existing_fps and (not t.isrc or t.isrc not in existing_isrcs)
            ]

            reports.append(
                DiscoveryAttemptReport(
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

        # Sort by advisor score DESC, trim to exact playlist_size
        tracks_scores.sort(key=lambda x: x[1], reverse=True)
        tracks = [t for t, _ in tracks_scores[: config.playlist_size]]

        if len(tracks) < config.playlist_size:
            logger.warning(
                f"playlist_size not reached ({len(tracks)}/{config.playlist_size}) "
                f"after {config.max_attempts} attempt(s)",
                extra={"found": len(tracks), "target": config.playlist_size},
            )

        if config.dry_run:
            logger.info("Dry-run mode: skipping playlist creation.")
            return DiscoveryResult(playlist=None, reports=reports, tracks=tracks)

        playlist = await self._provider_library.create_playlist(
            name=f"[{__project_name__.capitalize()}] - {self._advisor_client.display_name} - {datetime.now(UTC).isoformat()}",
            tracks=tracks,
        )
        return DiscoveryResult(playlist=playlist, reports=reports, tracks=tracks)

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
        return sorted(tracks_suggested, key=lambda t: t.score or 0, reverse=True)

    async def _reconcile_tracks(
        self,
        tracks_suggested: list[TrackSuggested],
        limit: int,
    ) -> list[tuple[Track, Score]]:
        """Reconciles suggested tracks with the provider.

        Args:
            tracks_suggested: A list of tracks suggested by the advisor.
            limit: The maximum number of search candidates per suggestion.

        Returns:
            A list of (reconciled track, advisor score) pairs.
        """
        tracks_reconciled: list[tuple[Track, Score]] = []

        for track_suggested in tracks_suggested:
            candidates = await self._provider_library.search_tracks(
                track=track_suggested.name,
                artists=track_suggested.artists,
                page_size=limit,
                log_enabled=False,
            )

            best_match = self._track_reconciler.reconcile(
                track_suggested=track_suggested,
                candidates=candidates,
            )
            if best_match:
                tracks_reconciled.append((best_match, track_suggested.score or 0.0))
                logger.debug(f"Track reconciled: '{track_suggested}'")
            else:
                logger.debug(f"Track not reconciled: '{track_suggested}'")

        return tracks_reconciled

    async def _deduplicate_tracks(
        self,
        user: User,
        tracks_reconciled: list[tuple[Track, Score]],
    ) -> list[tuple[Track, Score]]:
        """Deduplicate tracks that are already in the user's library.

        Args:
            user: The user to check against.
            tracks_reconciled: A list of (track, score) pairs to filter.

        Returns:
            A list of (track, score) pairs not in the user's library.
        """
        tracks_new: list[tuple[Track, Score]] = []

        known_identifiers = await self._track_repository.get_known_identifiers(
            user_id=user.id,
            isrcs=[track.isrc for track, _ in tracks_reconciled if track.isrc],
            fingerprints=[track.fingerprint for track, _ in tracks_reconciled],
        )

        for track, score in tracks_reconciled:
            if known_identifiers.is_known(track):
                logger.debug(f"Excluded '{track}'")
                continue

            tracks_new.append((track, score))

        logger.debug(
            f"Discovery:\n- {'\n- '.join([f"'{t}'" for t, _ in tracks_new])}" if tracks_new else "Discovery: None"
        )
        return tracks_new
