import logging
from dataclasses import dataclass
from datetime import datetime
from fnmatch import fnmatchcase

from museflow.application.inputs.history import ImportStreamingHistoryConfigInput
from museflow.application.inputs.history import StreamingHistoryEntryInput
from museflow.application.ports.progress import ProgressPort
from museflow.application.ports.providers.history import StreamingHistoryPort
from museflow.application.ports.storage import FileStoragePort
from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.domain.entities.track import ProviderLink
from museflow.domain.entities.track import Track
from museflow.domain.entities.user import User
from museflow.domain.enums import MusicProvider
from museflow.domain.enums import ProgressStep
from museflow.domain.exceptions import StreamingHistoryFilesNotFoundError
from museflow.domain.exceptions import StreamingHistoryInvalidFormatError
from museflow.domain.utils.text import generate_fingerprint
from museflow.domain.value_objects.progress import StepAdvanced
from museflow.domain.value_objects.progress import StepDone
from museflow.domain.value_objects.progress import StepStarted
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

    Parses the provider's streaming history files found under the given prefix of the user's file storage, filters
    entries by minimum playback duration, deduplicates track IDs, and bulk-upserts them into the repository directly
    from file metadata — no external API calls. The files are left in the storage: the caller deletes them.
    """

    def __init__(
        self,
        uow: UnitOfWorkPort,
        streaming_history: StreamingHistoryPort,
        file_storage: FileStoragePort,
        progress: ProgressPort,
    ) -> None:
        self._uow = uow
        self._streaming_history = streaming_history
        self._file_storage = file_storage
        self._progress = progress

    async def import_history(
        self,
        user: User,
        config: ImportStreamingHistoryConfigInput,
    ) -> ImportStreamingHistoryReport:
        # The export also holds files of other kinds: only the provider's streaming history files are read
        pattern = self._streaming_history.file_pattern
        keys = [
            key
            for key in await self._file_storage.list_keys(user_id=user.id, prefix=config.prefix)
            if fnmatchcase(_file_name(key), pattern)
        ]
        if not keys:
            raise StreamingHistoryFilesNotFoundError(f"No {pattern} files found under: {config.prefix}")

        # Collect all play events per track across all files, keyed by fingerprint.
        # When two provider_ids resolve to the same fingerprint, their play times are merged.
        # The first entry seen for a given fingerprint is kept as representative metadata.
        track_metadata: dict[str, StreamingHistoryEntryInput] = {}  # fingerprint → representative entry
        track_play_times: dict[str, list[datetime]] = {}  # fingerprint → all played_at timestamps
        items_read = items_skipped_no_timestamp = items_skipped_short_play = items_skipped_no_track_id = 0

        await self._progress.publish(StepStarted(step=ProgressStep.HISTORY_READ, total=len(keys)))
        for files_done, key in enumerate(keys, start=1):
            content = await self._file_storage.get(user_id=user.id, key=key)
            try:
                entries, stats = await self._streaming_history.parse_file(
                    content=content,
                    min_ms_played=config.min_ms_played,
                )
            except StreamingHistoryInvalidFormatError as e:
                raise StreamingHistoryInvalidFormatError(f"{_file_name(key)}: {e}") from e

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
            await self._progress.publish(
                StepAdvanced(step=ProgressStep.HISTORY_READ, done=files_done, total=len(keys))
            )
        await self._progress.publish(StepDone(step=ProgressStep.HISTORY_READ))

        unique_fingerprints = set(track_metadata.keys())
        logger.debug(f"Collected {len(unique_fingerprints)} unique fingerprints.")

        # Purge only once every file is parsed: a malformed file then aborts the import before anything is deleted.
        tracks_purged = 0
        if config.purge:
            async with self._uow as uow:
                orphan_ids = await uow.tracks.unlink_provider(user_id=user.id, provider=MusicProvider.SPOTIFY)
                tracks_purged = await uow.tracks.delete(user_id=user.id, track_ids=orphan_ids)
            logger.debug("History tracks purged.")

        # Upsert every track, known or not (its metadata and provider link are refreshed), then save its plays: a play
        # already saved is skipped, so a re-import of the same files adds none.
        logger.debug(f"Upserting {len(unique_fingerprints)} tracks and their plays from file metadata.")
        tracks_created = plays_created = 0
        fingerprints = sorted(unique_fingerprints)

        await self._progress.publish(StepStarted(step=ProgressStep.HISTORY_SAVE, total=len(fingerprints)))
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
            tracks_done = min(offset + config.batch_size, len(fingerprints))
            await self._progress.publish(
                StepAdvanced(step=ProgressStep.HISTORY_SAVE, done=tracks_done, total=len(fingerprints))
            )
        await self._progress.publish(StepDone(step=ProgressStep.HISTORY_SAVE))

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


def _file_name(key: str) -> str:
    return key.rsplit("/", 1)[-1]
