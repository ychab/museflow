import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field

from museflow.domain.enums import JobKind
from museflow.domain.enums import JobStatus


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: JobKind
    status: JobStatus
    input: dict[str, Any]
    result: dict[str, Any] | None = Field(description="What the job returned, once done")
    error: str | None = Field(description="Why the job failed, once failed")
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
