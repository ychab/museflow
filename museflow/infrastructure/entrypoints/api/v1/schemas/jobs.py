import uuid
from datetime import datetime
from typing import Annotated
from typing import Final
from typing import Literal

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import TypeAdapter

from museflow.domain.enums import EnrichField
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


class TrackEnrichJobInputResponse(BaseModel):
    fields: list[EnrichField]


class TrackEnrichJobResultResponse(BaseModel):
    """The report of the enrichment. A job resumed after its worker died counts the tracks enriched by its last try
    only."""

    enriched_count: int
    error_count: int = Field(description="The batches of tracks that failed: their tracks are left for the next job")


class TasteBuildJobInputResponse(BaseModel):
    name: str
    title: str
    rated_only: bool


class TasteBuildJobResultResponse(BaseModel):
    """The profile built: read it by its name."""

    name: str
    tracks_count: int = Field(description="The tracks the profile was built from")


class BaseJobResponse(BaseModel):
    """What every kind of job answers; each kind adds its `kind`, `input` and `result`."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: JobStatus
    error: str | None = Field(description="Why the job failed, once failed: the name of the error")
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class TrackHistoryImportJobResponse(BaseJobResponse):
    kind: Literal[JobKind.TRACK_HISTORY_IMPORT]
    input: TrackHistoryImportJobInputResponse
    result: TrackHistoryImportJobResultResponse | None = Field(description="What the job returned, once done")


class TrackEnrichJobResponse(BaseJobResponse):
    kind: Literal[JobKind.TRACK_ENRICH]
    input: TrackEnrichJobInputResponse
    result: TrackEnrichJobResultResponse | None = Field(description="What the job returned, once done")


class TasteBuildJobResponse(BaseJobResponse):
    kind: Literal[JobKind.TASTE_BUILD]
    input: TasteBuildJobInputResponse
    result: TasteBuildJobResultResponse | None = Field(description="What the job returned, once done")


# A job of any kind, its input and result typed by its `kind`
JobResponse = Annotated[
    TrackHistoryImportJobResponse | TrackEnrichJobResponse | TasteBuildJobResponse,
    Field(discriminator="kind"),
]

JobResponseAdapter: Final[TypeAdapter[JobResponse]] = TypeAdapter(JobResponse)
