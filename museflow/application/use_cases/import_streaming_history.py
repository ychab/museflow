import dataclasses
import logging
from dataclasses import dataclass

from museflow.application.inputs.history import StreamingHistoryEntry
from museflow.application.inputs.history import StreamingHistoryImportConfigInput
from museflow.application.ports.providers.history import StreamingHistoryPort
from museflow.application.ports.repositories.music import TrackRepository
from museflow.domain.entities.music import Track
from museflow.domain.entities.user import User
from museflow.domain.exceptions import StreamingHistoryDirectoryNotFound
from museflow.domain.types import MusicProvider

logger = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class ImportStreamingHistoryReport:
    items_read: int = 0
    items_skipped_no_timestamp: int = 0
    items_skipped_short_play: int = 0
    items_skipped_no_track_id: int = 0

    unique_track_ids: int = 0

    tracks_already_known: int = 0
    tracks_played_at_updated: int = 0

    tracks_created: int = 0
    tracks_purged: int = 0


class ImportStreamingHistoryUseCase:
    """
    Import a user's Spotify streaming history from exported JSON files.

    Parses all JSON files in the given directory, filters entries by minimum
    playback duration, deduplicates track IDs, and bulk-upserts them into
    the repository directly from file metadata — no external API calls.
    """

    def __init__(self, track_repository: TrackRepository, streaming_history: StreamingHistoryPort) -> None:
        self._track_repository = track_repository
        self._streaming_history = streaming_history

    async def import_history(
        self,
        user: User,
        config: StreamingHistoryImportConfigInput,
    ) -> ImportStreamingHistoryReport:
        # Validate directory
        if not config.directory.exists() or not config.directory.is_dir():
            raise StreamingHistoryDirectoryNotFound(f"Directory not found: {config.directory}")

        # Validate files
        json_files = sorted(config.directory.glob("*.json"))
        if not json_files:
            raise StreamingHistoryDirectoryNotFound(f"No JSON files found in: {config.directory}")

        # Purge if requested
        tracks_purged = 0
        if config.purge:
            tracks_purged = await self._track_repository.purge(
                user_id=user.id,
                provider=MusicProvider.SPOTIFY,
            )
            logger.info("History tracks purged.\n")

        # Collect unique track IDs with their latest played_at and metadata across all files
        tracks_data: dict[str, StreamingHistoryEntry] = {}  # provider_id → latest entry
        items_read = items_skipped_no_timestamp = items_skipped_short_play = items_skipped_no_track_id = 0

        for path in json_files:
            entries, stats = await self._streaming_history.parse_file(path=path, min_ms_played=config.min_ms_played)

            for entry in entries:
                if entry.provider_id not in tracks_data or entry.played_at > tracks_data[entry.provider_id].played_at:
                    tracks_data[entry.provider_id] = entry

            items_read += stats.items_read
            items_skipped_no_timestamp += stats.items_skipped_no_timestamp
            items_skipped_short_play += stats.items_skipped_short_play
            items_skipped_no_track_id += stats.items_skipped_no_track_id

        track_provider_ids = set(tracks_data.keys())
        logger.info(f"Collected {len(track_provider_ids)} unique track ID's.")

        # Filter already-known IDs
        if not track_provider_ids:
            known_ids: frozenset[str] = frozenset()
        else:
            known_ids = await self._track_repository.get_known_provider_ids(
                user_id=user.id,
                provider=MusicProvider.SPOTIFY,
                provider_ids=list(track_provider_ids),
            )
        unknown_ids = track_provider_ids - known_ids
        logger.info(f"Collected {len(unknown_ids)} unknown track ID's.")

        # Refresh played_at for already-known tracks (bulk_upsert uses GREATEST — safe to re-run)
        tracks_played_at_updated = 0
        if known_ids:
            known_tracks = await self._track_repository.get_list(
                user_id=user.id,
                provider=MusicProvider.SPOTIFY,
                provider_ids=list(known_ids),
            )
            updated_tracks = [
                dataclasses.replace(track, played_at=tracks_data[track.provider_id].played_at)
                for track in known_tracks
            ]
            await self._track_repository.bulk_upsert(tracks=updated_tracks, batch_size=config.batch_size)
            tracks_played_at_updated = len(updated_tracks)
            logger.info(f"Refreshed played_at for {tracks_played_at_updated} already-known tracks.")

        # Build Track entities directly from file metadata and upsert in batches
        logger.info(f"\nUpserting {len(unknown_ids)} new tracks from file metadata.")
        tracks_created = 0
        unknown_entries = [tracks_data[pid] for pid in unknown_ids]

        for offset in range(0, len(unknown_entries), config.batch_size):
            chunk = unknown_entries[offset : offset + config.batch_size]
            chunk_tracks = [
                Track(
                    user_id=user.id,
                    provider=MusicProvider.SPOTIFY,
                    provider_id=entry.provider_id,
                    name=entry.name,
                    artists=[entry.artist],
                    album_name=entry.album_name,
                    played_at=entry.played_at,
                )
                for entry in chunk
            ]
            _, created = await self._track_repository.bulk_upsert(
                tracks=chunk_tracks,
                batch_size=config.batch_size,
            )
            tracks_created += created
            logger.info(
                f"... upserted {min(offset + config.batch_size, len(unknown_entries))} / {len(unknown_entries)}..."
            )

        return ImportStreamingHistoryReport(
            items_read=items_read,
            items_skipped_no_timestamp=items_skipped_no_timestamp,
            items_skipped_short_play=items_skipped_short_play,
            items_skipped_no_track_id=items_skipped_no_track_id,
            unique_track_ids=len(track_provider_ids),
            tracks_already_known=len(known_ids),
            tracks_played_at_updated=tracks_played_at_updated,
            tracks_created=tracks_created,
            tracks_purged=tracks_purged,
        )
