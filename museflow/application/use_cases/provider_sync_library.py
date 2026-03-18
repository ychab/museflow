import logging
from collections.abc import Awaitable
from collections.abc import Callable
from dataclasses import dataclass
from dataclasses import field
from dataclasses import replace
from typing import Any

from museflow.application.inputs.sync import SyncConfigInput
from museflow.application.ports.providers.library import ProviderLibraryPort
from museflow.application.ports.repositories.music import ArtistRepository
from museflow.application.ports.repositories.music import TrackRepository
from museflow.domain.entities.user import User
from museflow.domain.types import TrackSource

logger = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class SyncReport:
    """Reports the outcome of a library synchronization operation.

    Contains counts of purged, created, and updated entities, as well as any
    errors encountered during the synchronization process.
    """

    purge_artist: int = 0
    purge_track: int = 0

    artist_created: int = 0
    artist_updated: int = 0

    track_created: int = 0
    track_updated: int = 0

    errors: list[str] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0


class ProviderSyncLibraryUseCase:
    """Synchronizes a user's music library with a music provider.

    This use case orchestrates the fetching of music data (artists, tracks) from
    an external music provider and persists it into the application's database.
    It supports purging existing data before synchronization and provides a detailed
    report of the operation.
    """

    def __init__(
        self,
        provider_library: ProviderLibraryPort,
        artist_repository: ArtistRepository,
        track_repository: TrackRepository,
    ) -> None:
        self._provider_library = provider_library
        self._artist_repository = artist_repository
        self._track_repository = track_repository

    async def sync_library(
        self,
        user: User,
        config: SyncConfigInput,
    ) -> SyncReport:
        report = SyncReport()

        # First of all, purge items if required.
        if config.has_purge():
            if config.purge_all or config.purge_artist_top:
                report = await self._purge_entity(
                    report=report,
                    report_field_purge="purge_artist",
                    user=user,
                    entity_name="artists",
                    purge_callback=lambda: self._artist_repository.purge(user_id=user.id),
                )

            if config.purge_all or config.purge_track_top or config.purge_track_saved or config.purge_track_playlist:
                report = await self._purge_entity(
                    report=report,
                    report_field_purge="purge_track",
                    user=user,
                    entity_name="tracks",
                    purge_callback=lambda: self._track_repository.purge(
                        user_id=user.id,
                        sources=TrackSource.from_flags(
                            top=config.purge_track_top,
                            saved=config.purge_track_saved,
                            playlist=config.purge_track_playlist,
                        ),
                    ),
                )

            if report.has_errors:
                return report

        # Then fetch and upsert top artists.
        if config.sync_all or config.sync_artist_top:
            report = await self._sync_entity(
                report=report,
                report_field_created="artist_created",
                report_field_updated="artist_updated",
                user=user,
                entity_name="top artists",
                fetch_func=lambda: self._provider_library.get_top_artists(
                    page_size=config.page_size,
                    time_range=config.time_range,
                ),
                upsert_func=lambda items: self._artist_repository.bulk_upsert(
                    artists=items,
                    batch_size=config.batch_size,
                ),
            )

        # Then fetch and upsert top tracks.
        if config.sync_all or config.sync_track_top:
            report = await self._sync_entity(
                report=report,
                report_field_created="track_created",
                report_field_updated="track_updated",
                user=user,
                entity_name="top tracks",
                fetch_func=lambda: self._provider_library.get_top_tracks(
                    page_size=config.page_size,
                    time_range=config.time_range,
                ),
                upsert_func=lambda items: self._track_repository.bulk_upsert(
                    tracks=items,
                    batch_size=config.batch_size,
                ),
            )

        # Then fetch and upsert saved tracks.
        if config.sync_all or config.sync_track_saved:
            report = await self._sync_entity(
                report=report,
                report_field_created="track_created",
                report_field_updated="track_updated",
                user=user,
                entity_name="saved tracks",
                fetch_func=lambda: self._provider_library.get_saved_tracks(
                    page_size=config.page_size,
                ),
                upsert_func=lambda items: self._track_repository.bulk_upsert(
                    tracks=items,
                    batch_size=config.batch_size,
                ),
            )

        # Then fetch and upsert playlist tracks.
        if config.sync_all or config.sync_track_playlist:
            report = await self._sync_entity(
                report=report,
                report_field_created="track_created",
                report_field_updated="track_updated",
                user=user,
                entity_name="playlist tracks",
                fetch_func=lambda: self._provider_library.get_playlist_tracks(
                    page_size=config.page_size,
                ),
                upsert_func=lambda items: self._track_repository.bulk_upsert(
                    tracks=items,
                    batch_size=config.batch_size,
                ),
            )

        return report

    async def _purge_entity(
        self,
        report: SyncReport,
        report_field_purge: str,
        user: User,
        entity_name: str,
        purge_callback: Callable[[], Awaitable[int]],
    ) -> SyncReport:
        logger.info(f"About purging {entity_name} for user {user.id}...")

        try:
            count = await purge_callback()
        except Exception:
            logger.exception(f"An error occurred while purging {entity_name} for user {user.id}")
            report = replace(report, errors=report.errors + [f"An error occurred while purging your {entity_name}."])
        else:
            logger.info(f"Successfully purged {count} {entity_name} for user {user.id}")
            report_updates: dict[str, Any] = {report_field_purge: count}
            report = replace(report, **report_updates)

        return report

    async def _sync_entity[T](
        self,
        report: SyncReport,
        report_field_created: str,
        report_field_updated: str,
        user: User,
        entity_name: str,
        fetch_func: Callable[[], Awaitable[list[T]]],
        upsert_func: Callable[[list[T]], Awaitable[tuple[list[Any], int]]],
    ) -> SyncReport:
        logger.info(f"About synchronizing {entity_name} for user {user.id}...")

        # Fetch step
        try:
            items = await fetch_func()
        except Exception:
            logger.exception(f"An error occurred while fetching {entity_name} for user {user.id}")
            report = replace(report, errors=report.errors + [f"An error occurred while fetching {entity_name}."])
            return report
        else:
            logger.info(f"Fetched {len(items)} {entity_name} for user {user.id}")

        # Upsert step
        try:
            ids, created = await upsert_func(items)
        except Exception:
            logger.exception(f"An error occurred while upserting {entity_name} for user {user.id}")
            report = replace(report, errors=report.errors + [f"An error occurred while saving {entity_name}."])
            return report
        else:
            logger.info(f"Upserted {len(ids)} {entity_name} for user {user.id}")

        report_updates: dict[str, Any] = {
            report_field_created: getattr(report, report_field_created) + created,
            report_field_updated: getattr(report, report_field_updated) + (len(ids) - created),
        }
        return replace(report, **report_updates)
