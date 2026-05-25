from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True, kw_only=True)
class StreamingHistoryImportConfigInput:
    directory: Path
    min_ms_played: int = 30_000
    batch_size: int = 20
    purge: bool = False


@dataclass(frozen=True, kw_only=True)
class StreamingHistoryEntry:
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
