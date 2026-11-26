import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field

from museflow.domain.enums import JobKind
from museflow.domain.enums import JobStatus
from museflow.domain.enums import MusicProvider


class TrackHistoryImportJobInputResponse(BaseModel):
    """The options of the import; where its files are stays internal."""

    provider: MusicProvider
    min_ms_played: int
    purge: bool


class TrackHistoryImportJobResultResponse(BaseModel):
    """The report of the import. A job resumed after its worker died counts the plays created by its last try only."""

    items_read: int
    items_skipped_no_timestamp: int
    items_skipped_short_play: int
    items_skipped_no_track_id: int
    unique_track_ids: int
    tracks_already_known: int
    plays_total: int
    plays_created: int
    tracks_created: int
    tracks_purged: int


class TrackHistoryImportJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: Literal[JobKind.TRACK_HISTORY_IMPORT]
    status: JobStatus
    input: TrackHistoryImportJobInputResponse
    result: TrackHistoryImportJobResultResponse | None = Field(description="What the job returned, once done")
    error: str | None = Field(description="Why the job failed, once failed: the name of the error")
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


# A job of any kind: one response per kind, its input and result typed. The next kind turns it into a union
# discriminated by `kind` (`Annotated[A | B, Field(discriminator="kind")]`), validated with a `TypeAdapter`.
JobResponse = TrackHistoryImportJobResponse
