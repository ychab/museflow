from dataclasses import dataclass
from datetime import datetime

from pydantic import BaseModel
from pydantic import ConfigDict

from museflow.domain.enums import MusicProvider


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


class ImportStreamingHistoryJobInput(BaseModel):
    """What a history import job runs on, kept as its input: where its files are, and the options of the import.

    A Pydantic model: the job keeps it as JSON (`model_dump(mode="json")`), read back with `model_validate`.
    """

    model_config = ConfigDict(frozen=True)

    prefix: str  # every file of the job, in the user's file storage: the archive, then the files extracted from it
    provider: MusicProvider
    min_ms_played: int = ImportStreamingHistoryConfigInput.min_ms_played
    purge: bool = ImportStreamingHistoryConfigInput.purge

    @property
    def archive_key(self) -> str:
        return f"{self.prefix}/archive.zip"

    @property
    def files_prefix(self) -> str:
        return f"{self.prefix}/files"
