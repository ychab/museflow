import uuid
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import Enum
from sqlalchemy import ForeignKey
from sqlalchemy import Index
from sqlalchemy import Integer
from sqlalchemy import Interval
from sqlalchemy import Numeric
from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from museflow.domain.entities.llm import LLMUsageRecord
from museflow.domain.enums import LLMOperation
from museflow.domain.value_objects.llm import LLMUsage
from museflow.infrastructure.adapters.database.models.base import Base
from museflow.infrastructure.adapters.database.models.base import DatetimeTrackMixin
from museflow.infrastructure.adapters.database.models.base import UUIDIdMixin


class LLMUsageModel(UUIDIdMixin, DatetimeTrackMixin, Base, kw_only=True):
    """One row per (command run, step, model)."""

    __tablename__ = "museflow_llm_usage"
    __table_args__ = (Index("ix_museflow_llm_usage_user_id_created_at", "user_id", "created_at"),)

    # Identity / FK
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("museflow_user.id", ondelete="CASCADE"),
        nullable=False,
        sort_order=-50,
    )
    run_id: Mapped[uuid.UUID] = mapped_column(nullable=False, sort_order=-49)
    operation: Mapped[LLMOperation] = mapped_column(Enum(LLMOperation), nullable=False, sort_order=-48)

    # The history outlives the profile or the playlist it paid for.
    profile_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("museflow_taste_profile.id", ondelete="SET NULL"),
        nullable=True,
        default=None,
    )
    playlist_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("museflow_playlist.id", ondelete="SET NULL"),
        nullable=True,
        default=None,
    )

    # Usage
    step: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(255), nullable=False)
    calls: Mapped[int] = mapped_column(Integer, nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    reasoning_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    cost: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    duration: Mapped[timedelta] = mapped_column(Interval, nullable=False)

    @classmethod
    def from_entity(cls, entity: LLMUsageRecord) -> LLMUsageModel:
        usage_db = cls(
            id=entity.id,
            user_id=entity.user_id,
            run_id=entity.run_id,
            operation=entity.operation,
            profile_id=entity.profile_id,
            playlist_id=entity.playlist_id,
            step=entity.usage.step,
            model=entity.usage.model,
            calls=entity.usage.calls,
            prompt_tokens=entity.usage.prompt_tokens,
            completion_tokens=entity.usage.completion_tokens,
            reasoning_tokens=entity.usage.reasoning_tokens,
            cost=entity.usage.cost,
            duration=entity.usage.duration,
        )
        # Not an init field: set it so that an imported row keeps the date of its run.
        usage_db.created_at = entity.created_at
        return usage_db

    def to_entity(self) -> LLMUsageRecord:
        return LLMUsageRecord(
            id=self.id,
            user_id=self.user_id,
            run_id=self.run_id,
            operation=self.operation,
            usage=LLMUsage(
                step=self.step,
                model=self.model,
                calls=self.calls,
                prompt_tokens=self.prompt_tokens,
                completion_tokens=self.completion_tokens,
                reasoning_tokens=self.reasoning_tokens,
                cost=self.cost,
                duration=self.duration,
            ),
            profile_id=self.profile_id,
            playlist_id=self.playlist_id,
            created_at=self.created_at,
        )
