import asyncio
import itertools
import logging
from dataclasses import dataclass
from pathlib import Path

import ijson

from museflow.application.inputs.history import ImportStreamingHistoryConfigInput
from museflow.application.ports.providers.library import ProviderLibraryPort
from museflow.application.ports.repositories.music import TrackRepository
from museflow.domain.entities.user import User
from museflow.domain.exceptions import StreamingHistoryDirectoryNotFound
from museflow.domain.exceptions import StreamingHistoryInvalidFormat
from museflow.domain.types import MusicProvider
from museflow.domain.types import TrackSource

logger = logging.getLogger(__name__)

type _CounterRead = int
type _CounterSkippedDuration = int
type _CounterSkippedUri = int


@dataclass(frozen=True, kw_only=True)
class ImportStreamingHistoryReport:
    items_read: int = 0
    items_skipped_duration: int = 0
    items_skipped_no_uri: int = 0

    unique_track_ids: int = 0

    tracks_already_known: int = 0
    tracks_fetched: int = 0
    tracks_created: int = 0
    tracks_purged: int = 0


class ImportStreamingHistoryUseCase:
    """Import a user's Spotify streaming history from exported JSON files.

    Parses all JSON files in the given directory, filters entries by minimum
    playback duration, deduplicates track IDs, fetches unknown tracks from the
    provider, and bulk-upserts them into the repository.

    Attributes:
        _provider_library: Port to fetch track metadata from the music provider.
        _track_repository: Repository for persisting and querying tracks.
    """

    def __init__(self, provider_library: ProviderLibraryPort, track_repository: TrackRepository) -> None:
        self._provider_library = provider_library
        self._track_repository = track_repository

    async def import_history(
        self,
        user: User,
        config: ImportStreamingHistoryConfigInput,
    ) -> ImportStreamingHistoryReport:
        # Validate directory
        if not config.directory.exists() or not config.directory.is_dir():
            raise StreamingHistoryDirectoryNotFound(f"Directory not found: {config.directory}")

        json_files = sorted(config.directory.glob("*.json"))
        if not json_files:
            raise StreamingHistoryDirectoryNotFound(f"No JSON files found in: {config.directory}")

        # Purge if requested
        tracks_purged = 0
        if config.purge:
            tracks_purged = await self._track_repository.purge(
                user_id=user.id,
                provider=MusicProvider.SPOTIFY,
                sources=TrackSource.HISTORY,
            )
            logger.info("History tracks purged.\n")

        # Heavily collect unique track IDs from all files AT ONCE
        track_provider_ids: set[str] = set()
        items_read = 0
        items_skipped_duration = 0
        items_skipped_no_uri = 0

        for path in json_files:
            ids, read, skipped_dur, skipped_uri = await asyncio.to_thread(
                self._parse_history_file,
                path=path,
                min_ms_played=config.min_ms_played,
            )
            track_provider_ids.update(ids)
            items_read += read
            items_skipped_duration += skipped_dur
            items_skipped_no_uri += skipped_uri
        logger.info(f"Collected {len(track_provider_ids)} unique track ID's.")

        # Filter already-known IDs
        known_ids = await self._track_repository.get_known_provider_ids(
            user_id=user.id,
            provider=MusicProvider.SPOTIFY,
            provider_ids=list(track_provider_ids),
        )
        unknown_ids = track_provider_ids - known_ids
        logger.info(f"Collected {len(unknown_ids)} unknown track ID's.")

        # Fetch tracks from the provider in chunks and upsert each chunk immediately.
        # It releases memory but also allows re-running the command without a purge in case of a rate limit bottleneck.
        logger.info(f"\nAbout fetching and upserting {len(unknown_ids)} track's metadata.")
        tracks_fetched = 0
        tracks_created = 0
        for chunk in itertools.batched(unknown_ids, config.batch_size, strict=False):
            logger.info(f"... fetching {tracks_fetched + len(chunk)} / {len(unknown_ids)}...")

            if config.fetch_bulk:
                chunk_tracks = await self._provider_library.get_tracks_by_ids(list(chunk))
            else:
                chunk_tracks = list(
                    await asyncio.gather(*[self._provider_library.get_track_by_id(tid) for tid in chunk])
                )
            tracks_fetched += len(chunk_tracks)

            _, created = await self._track_repository.bulk_upsert(
                tracks=list(chunk_tracks),
                batch_size=config.batch_size,
            )
            tracks_created += created

        # Finally, build and return report
        return ImportStreamingHistoryReport(
            items_read=items_read,
            items_skipped_duration=items_skipped_duration,
            items_skipped_no_uri=items_skipped_no_uri,
            unique_track_ids=len(track_provider_ids),
            tracks_already_known=len(known_ids),
            tracks_fetched=tracks_fetched,
            tracks_created=tracks_created,
            tracks_purged=tracks_purged,
        )

    @staticmethod
    def _parse_history_file(
        path: Path, min_ms_played: int
    ) -> tuple[set[str], _CounterRead, _CounterSkippedDuration, _CounterSkippedUri]:
        """Parse a single streaming history JSON file and extract track IDs with counters.

        Runs synchronously and is intended to be offloaded via ``asyncio.to_thread``.
        Streams the file using ijson to avoid loading the entire JSON into memory.

        Args:
            path: Path to the JSON history file to parse.
            min_ms_played: Minimum playback duration in milliseconds; entries below
                this threshold are skipped and counted as skipped-duration.

        Returns:
            A 4-tuple of:
            - set of Spotify track IDs extracted from valid entries,
            - number of entries read,
            - number of entries skipped due to insufficient playback duration,
            - number of entries skipped due to a missing or invalid track URI.

        Raises:
            StreamingHistoryInvalidFormat: If the file cannot be parsed as valid JSON.
        """
        track_ids: set[str] = set()

        items_read = 0
        items_skipped_duration = 0
        items_skipped_no_uri = 0

        try:
            with open(path, "rb") as f:
                for item in ijson.items(f, "item"):
                    items_read += 1

                    if item.get("ms_played", 0) < min_ms_played:
                        items_skipped_duration += 1
                        continue

                    uri = item.get("spotify_track_uri")
                    if uri is None:
                        items_skipped_no_uri += 1
                        continue

                    parts = uri.split(":")
                    if len(parts) != 3 or parts[1] != "track":
                        items_skipped_no_uri += 1
                        continue

                    track_ids.add(parts[2])
        except Exception as exc:
            raise StreamingHistoryInvalidFormat(f"Failed to parse {path}: {exc}") from exc

        return track_ids, items_read, items_skipped_duration, items_skipped_no_uri
