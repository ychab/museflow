import logging
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
from museflow.domain.exceptions import DiscoveryTrackNoReconciledFound
from museflow.domain.exceptions import DiscoveryTrackNoSeedFound
from museflow.domain.exceptions import DiscoveryTrackNoSimilarFound
from museflow.domain.exceptions import SimilarTrackResponseException
from museflow.domain.services.reconciler import TrackReconciler
from museflow.domain.types import MusicProvider
from museflow.domain.types import TrackSource

logger = logging.getLogger(__name__)


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

    async def create_suggestions_playlist(self, user: User, config: DiscoveryConfigInput) -> Playlist:
        """Creates a playlist of suggested tracks for a user.

        The process involves gathering seed tracks from the user's library,
        finding similar tracks using an advisor, reconciling them with a provider,
        excluding tracks the user already knows, and finally creating a playlist.

        Args:
            user: The user for whom to create the playlist.
            config: The configuration for the discovery process.

        Returns:
            The newly created playlist.

        Raises:
            DiscoveryTrackNoSeedFound: If no seed tracks are found.
            DiscoveryTrackNoSimilarFound: If no similar tracks are found.
            DiscoveryTrackNoReconciledFound: If no tracks can be reconciled.
            DiscoveryTrackNoNew: If the user already knows all reconciled tracks.
        """
        # First, collect track seeds.
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
        )
        if not track_seeds:
            raise DiscoveryTrackNoSeedFound()
        logger.info(f"Seed tracks: {len(track_seeds)}\n")

        # Then get seed's similarities by the advisor.
        tracks_suggested = await self._get_similar_tracks(track_seeds=track_seeds, limit=config.similar_limit)
        if not tracks_suggested:
            raise DiscoveryTrackNoSimilarFound()
        logger.info(f"Suggested tracks: {len(tracks_suggested)}\n")

        # Then reconcile them with the provider.
        tracks_reconciled = await self._reconcile_tracks(
            tracks_suggested=tracks_suggested,
            limit=config.candidate_limit,
        )
        if not tracks_reconciled:
            raise DiscoveryTrackNoReconciledFound()
        logger.info(f"Reconciled tracks: {len(tracks_reconciled)}\n")

        # Then filter them to remove known tracks by the user.
        tracks = await self._deduplicate_tracks(user=user, tracks_reconciled=tracks_reconciled)
        if not tracks:
            raise DiscoveryTrackNoNew()
        logger.info(f"New tracks: {len(tracks)}\n")

        # Finally, save them into a dedicated playlist.
        return await self._provider_library.create_playlist(
            name=f"[{__project_name__.capitalize()}] - {self._advisor_client.display_name} - {datetime.now(UTC).isoformat()}",
            tracks=tracks,
        )

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
                logger.error(
                    f"An error occurred while fetching similar tracks: {e}",
                    extra={"track": track_seed},
                )
            else:
                tracks_suggested.extend(tracks_similar)
                logger.info(f"Track seed: '{track_seed}' => {len(tracks_similar)} suggestions")

        # Re-order them by score DESC.
        return sorted(tracks_suggested, key=lambda t: t.score or 0, reverse=True)

    async def _reconcile_tracks(self, tracks_suggested: list[TrackSuggested], limit: int) -> list[Track]:
        """Reconciles suggested tracks with the provider.

        This method attempts to find a match for each suggested track in the provider's library.

        Args:
            tracks_suggested: A list of tracks suggested by the advisor.

        Returns:
            A list of reconciled tracks.
        """
        tracks_reconciled: list[Track] = []

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
                tracks_reconciled.append(best_match)
                logger.info(f"Track reconciled: '{track_suggested}'")
            else:
                logger.warning(f"Track not reconciled: '{track_suggested}'")

        return tracks_reconciled

    async def _deduplicate_tracks(self, user: User, tracks_reconciled: list[Track]) -> list[Track]:
        """Deduplicate tracks that are already in the user's library.

        Args:
            user: The user to check against.
            tracks_reconciled: A list of reconciled tracks to filter.

        Returns:
            A list of tracks that are not in the user's library.
        """
        tracks_new: list[Track] = []

        known_identifiers = await self._track_repository.get_known_identifiers(
            user_id=user.id,
            isrcs=[track.isrc for track in tracks_reconciled if track.isrc],
            fingerprints=[track.fingerprint for track in tracks_reconciled],
        )

        for track in tracks_reconciled:
            if known_identifiers.is_known(track):
                logger.info(f"Excluded '{track}'")
                continue

            tracks_new.append(track)

        logger.info(f"\nDiscovery:\n- {'\n- '.join([f"'{t}'" for t in tracks_new])}")
        return tracks_new
