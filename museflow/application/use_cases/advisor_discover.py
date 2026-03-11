import logging
from dataclasses import dataclass
from datetime import UTC
from datetime import datetime

from museflow import __project_name__
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
from museflow.domain.types import SortOrder
from museflow.domain.types import TrackOrderBy

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DiscoveryConfig:
    """Configuration for the discovery process.

    Attributes:
        seed_top: Whether to use the user's top tracks as seeds.
        seed_saved: Whether to use the user's saved tracks as seeds.
        seed_order_by: The field to order the seed tracks by.
        seed_sort_order: The sort order for the seed tracks.
        seed_limit: The maximum number of seed tracks to use.
        similar_limit: The maximum number of similar tracks to fetch for each seed.
    """

    seed_top: bool | None = None
    seed_saved: bool | None = None
    seed_order_by: TrackOrderBy = TrackOrderBy.CREATED_AT
    seed_sort_order: SortOrder = SortOrder.ASC
    seed_limit: int = 50

    similar_limit: int = 5


class AdvisorDiscoverUseCase:
    """Use case for discovering new tracks based on a user's library."""

    def __init__(
        self,
        track_repository: TrackRepository,
        provider_library: ProviderLibraryPort,
        advisor_client: AdvisorClientPort,
    ) -> None:
        self._track_repository = track_repository
        self._provider_library = provider_library
        self._advisor_client = advisor_client

    async def create_suggestions_playlist(self, user: User, config: DiscoveryConfig) -> Playlist:
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
            DiscoveryTrackNoNew: If all reconciled tracks are already known by the user.
        """
        # First, gather track seeds.
        track_seeds = await self._track_repository.get_list(
            user_id=user.id,
            is_top=config.seed_top,
            is_saved=config.seed_saved,
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
        tracks = await self._reconcile_tracks(tracks_suggested=tracks_suggested)
        if not tracks:
            raise DiscoveryTrackNoReconciledFound()
        logger.info(f"Reconciled tracks: {len(tracks)}\n")

        # Then filter them to remove known tracks by the user.
        tracks = await self._exclude_known_tracks(user=user, tracks=tracks)
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
                    extra={
                        "tree_seed": {
                            "artist": track_seed.artists[0].name,
                            "track": track_seed.name,
                        },
                    },
                )
            else:
                tracks_suggested.extend(tracks_similar)
                logger.info(
                    f"Track seed: {track_seed.artists[0].name} - {track_seed.name} => {len(tracks_similar)} suggestions"
                )

        # Re-order them by score DESC.
        return sorted(tracks_suggested, key=lambda t: t.score or 0, reverse=True)

    async def _reconcile_tracks(self, tracks_suggested: list[TrackSuggested]) -> list[Track]:
        """Reconciles suggested tracks with the provider.

        This method attempts to find a match for each suggested track in the provider's library.

        Args:
            tracks_suggested: A list of tracks suggested by the advisor.

        Returns:
            A list of reconciled tracks.
        """
        tracks: list[Track] = []

        for track_suggested in tracks_suggested:
            tracks_reconciled = await self._provider_library.search_tracks(
                track=track_suggested.name,
                artists=track_suggested.artists,
                page_size=1,
                log_enabled=False,
            )
            if tracks_reconciled:
                tracks.append(tracks_reconciled[0])  # @TODO For now, blindly pick the first one. Needs a reconciler
                logger.info(f"Track reconciled: {track_suggested.name} - {track_suggested.artists}")
            else:
                logger.warning(f"Track not reconciled: {track_suggested.name} - {track_suggested.artists}")

        return tracks

    async def _exclude_known_tracks(self, user: User, tracks: list[Track]) -> list[Track]:
        """Excludes tracks that are already in the user's library.

        Args:
            user: The user to check against.
            tracks: A list of tracks to filter.

        Returns:
            A list of tracks that are not in the user's library.
        """
        # @TODO - For now, blindly sticks on ID's only (better to use fingerprint in addition)
        existing_tracks = await self._track_repository.get_by_ids(
            user_id=user.id,
            track_ids=[track.id for track in tracks],
        )

        existing_ids = [track.id for track in existing_tracks]
        return [track for track in tracks if track.id not in existing_ids]
