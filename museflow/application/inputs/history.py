from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, kw_only=True)
class ImportStreamingHistoryConfigInput:
    prefix: str  # where the export files are, in the user's file storage
    min_ms_played: int = 90_000
    batch_size: int = 20
    purge: bool = False


@dataclass(frozen=True, kw_only=True)
class StreamingHistoryEntryInput:
    name: str
    artist: str
    album_name: str | None
    provider_id: str
    played_at: datetime


@dataclass(frozen=True, kw_only=True)
class StreamingHistoryFileStats:
    items_read: int = 0
    items_skipped_no_timestamp: int = 0
    items_skipped_short_play: int = 0
    items_skipped_no_track_id: int = 0
