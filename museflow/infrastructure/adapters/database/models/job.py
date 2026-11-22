import uuid
from datetime import datetime
from typing import Any
from typing import Final

from sqlalchemy import DateTime
from sqlalchemy import Enum
from sqlalchemy import ForeignKey
from sqlalchemy import Index
from sqlalchemy import Text
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from museflow.domain.entities.job import Job as JobEntity
from museflow.domain.enums import JobKind
from museflow.domain.enums import JobStatus
from museflow.infrastructure.adapters.database.models.base import Base
from museflow.infrastructure.adapters.database.models.base import DatetimeTrackMixin
from museflow.infrastructure.adapters.database.models.base import UUIDIdMixin

# The PostgreSQL channel a new job is notified on, once its transaction commits: the relay listens to it
JOB_CHANNEL: Final[str] = "museflow_job"


class JobModel(UUIDIdMixin, DatetimeTrackMixin, Base, kw_only=True):
    __tablename__ = "museflow_job"
    __table_args__ = (
        # One active job of a kind per user: two enrichments at once would pay the LLM twice. The enum is stored by
        # name.
        Index(
            "uq_museflow_job_user_kind_active",
            "user_id",
            "kind",
            unique=True,
            postgresql_where=text("status IN ('PENDING', 'RUNNING')"),
        ),
        # The outbox: the relay reads the jobs not published yet, the oldest first; the index holds those only
        Index("ix_museflow_job_unpublished", "created_at", postgresql_where=text("published_at IS NULL")),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("museflow_user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        sort_order=-50,
    )
    kind: Mapped[JobKind] = mapped_column(Enum(JobKind), nullable=False)
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), nullable=False)

    input: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True, default=None)
    error: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)

    # Empty until the relay has published the task message: the outbox written in the transaction of the job
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)

    @classmethod
    def from_entity(cls, entity: JobEntity) -> JobModel:
        return cls(
            id=entity.id,
            user_id=entity.user_id,
            kind=entity.kind,
            status=entity.status,
            input=entity.input,
        )

    def to_entity(self) -> JobEntity:
        return JobEntity(
            id=self.id,
            user_id=self.user_id,
            kind=self.kind,
            status=self.status,
            input=self.input,
            result=self.result,
            error=self.error,
            created_at=self.created_at,
            started_at=self.started_at,
            finished_at=self.finished_at,
        )
