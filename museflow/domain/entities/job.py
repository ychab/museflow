import uuid
from dataclasses import dataclass
from dataclasses import field
from datetime import UTC
from datetime import datetime
from typing import Any

from museflow.domain.enums import JobKind
from museflow.domain.enums import JobStatus


@dataclass(frozen=True, kw_only=True)
class Job:
    """A flow a worker runs in the background for a user, and what the user can follow of it."""

    id: uuid.UUID = field(default_factory=uuid.uuid4)
    user_id: uuid.UUID
    kind: JobKind
    status: JobStatus = JobStatus.PENDING

    # JSON objects: what the job runs on (its options), then what it returns (its report)
    input: dict[str, Any] = field(default_factory=dict)
    result: dict[str, Any] | None = None
    # Why it failed, fit for the user: never a traceback
    error: str | None = None

    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    finished_at: datetime | None = None
