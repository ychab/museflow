import logging
from dataclasses import dataclass
from datetime import datetime

from museflow.application.inputs.history import ImportStreamingHistoryConfigInput
from museflow.application.inputs.history import StreamingHistoryEntryInput
from museflow.application.ports.providers.history import StreamingHistoryPort
from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.domain.entities.track import ProviderLink
from museflow.domain.entities.track import Track
from museflow.domain.entities.user import User
from museflow.domain.enums import MusicProvider
from museflow.domain.exceptions import StreamingHistoryDirectoryNotFoundError
from museflow.domain.utils.text import generate_fingerprint
from museflow.domain.value_objects.track import TrackPlay

logger = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class ImportStreamingHistoryReport:
    items_read: int = 0
    items_skipped_no_timestamp: int = 0
    items_skipped_short_play: int = 0
    items_skipped_no_track_id: int = 0

    unique_track_ids: int = 0

    tracks_already_known: int = 0
    plays_total: int = 0
    plays_created: int = 0  # plays not saved yet: 0 on a re-import of the same files

    tracks_created: int = 0
    tracks_purged: int = 0


class ImportStreamingHistoryUseCase:
    """
    Import a user's streaming history from a provider's exported JSON files.

    Parses the provider's streaming history files of the given directory, filters entries by minimum
    playback duration, deduplicates track IDs, and bulk-upserts them into
    the repository directly from file metadata — no external API calls.
    """

    def __init__(self, uow: UnitOfWorkPort, streaming_history: StreamingHistoryPort) -> None:
        self._uow = uow
        self._streaming_history = streaming_history

    async def import_history(
        self,
        user: User,
        config: ImportStreamingHistoryConfigInput,
    ) -> ImportStreamingHistoryReport:
        # Validate directory
        if not config.directory.exists() or not config.directory.is_dir():
            raise StreamingHistoryDirectoryNotFoundError(f"Directory not found: {config.directory}")

        # Validate files
        json_files = sorted(config.directory.glob(self._streaming_history.file_glob))
        if not json_files:
            raise StreamingHistoryDirectoryNotFoundError(
                f"No {self._streaming_history.file_glob} files found in: {config.directory}"
            )

        # Purge if requested
        tracks_purged = 0
        if config.purge:
            async with self._uow as uow:
                orphan_ids = await uow.tracks.unlink_provider(user_id=user.id, provider=MusicProvider.SPOTIFY)
                tracks_purged = await uow.tracks.delete(user_id=user.id, track_ids=orphan_ids)
            logger.info("History tracks purged.")

        # Collect all play events per track across all files, keyed by fingerprint.
        # When two provider_ids resolve to the same fingerprint, their play times are merged.
        # The first entry seen for a given fingerprint is kept as representative metadata.
        track_metadata: dict[str, StreamingHistoryEntryInput] = {}  # fingerprint → representative entry
        track_play_times: dict[str, list[datetime]] = {}  # fingerprint → all played_at timestamps
        items_read = items_skipped_no_timestamp = items_skipped_short_play = items_skipped_no_track_id = 0

        for path in json_files:
            entries, stats = await self._streaming_history.parse_file(path=path, min_ms_played=config.min_ms_played)

            for entry in entries:
                fp = generate_fingerprint(name=entry.name, artist_names=[entry.artist])
                if fp not in track_metadata:
                    track_metadata[fp] = entry
                    track_play_times[fp] = []
                track_play_times[fp].append(entry.played_at)

            items_read += stats.items_read
            items_skipped_no_timestamp += stats.items_skipped_no_timestamp
            items_skipped_short_play += stats.items_skipped_short_play
            items_skipped_no_track_id += stats.items_skipped_no_track_id

        unique_fingerprints = set(track_metadata.keys())
        logger.info(f"Collected {len(unique_fingerprints)} unique fingerprints.")

        # Upsert every track, known or not (its metadata and provider link are refreshed), then save its plays: a play
        # already saved is skipped, so a re-import of the same files adds none.
        logger.info(f"Upserting {len(unique_fingerprints)} tracks and their plays from file metadata.")
        tracks_created = plays_created = 0
        fingerprints = sorted(unique_fingerprints)

        for offset in range(0, len(fingerprints), config.batch_size):
            chunk_fps = fingerprints[offset : offset + config.batch_size]
            chunk_tracks = [
                Track(
                    user_id=user.id,
                    provider_links=[
                        ProviderLink(provider=MusicProvider.SPOTIFY, provider_id=track_metadata[fp].provider_id)
                    ],
                    name=track_metadata[fp].name,
                    artists=[track_metadata[fp].artist],
                    album_name=track_metadata[fp].album_name,
                )
                for fp in chunk_fps
            ]
            # One block per chunk: an interrupted import keeps the chunks already saved, each with its plays.
            async with self._uow as uow:
                track_ids, created = await uow.tracks.bulk_upsert(tracks=chunk_tracks, batch_size=config.batch_size)
                plays_created += await uow.track_plays.bulk_create(
                    [
                        TrackPlay(track_id=track_ids[track.fingerprint], played_at=played_at)
                        for track in chunk_tracks
                        for played_at in track_play_times[track.fingerprint]
                    ]
                )
            tracks_created += created
            logger.debug(f"... upserted {min(offset + config.batch_size, len(fingerprints))} / {len(fingerprints)}...")

        return ImportStreamingHistoryReport(
            items_read=items_read,
            items_skipped_no_timestamp=items_skipped_no_timestamp,
            items_skipped_short_play=items_skipped_short_play,
            items_skipped_no_track_id=items_skipped_no_track_id,
            unique_track_ids=len(unique_fingerprints),
            tracks_already_known=len(unique_fingerprints) - tracks_created,
            plays_created=plays_created,
            plays_total=sum(len(v) for v in track_play_times.values()),
            tracks_created=tracks_created,
            tracks_purged=tracks_purged,
        )
