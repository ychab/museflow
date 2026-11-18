import uuid
from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy import DateTime
from sqlalchemy import Enum
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from museflow.domain.entities.taste import TasteProfile as TasteProfileEntity
from museflow.domain.enums import TasteProfileStatus
from museflow.domain.value_objects.taste import TasteProfileData
from museflow.infrastructure.adapters.database.models.base import Base
from museflow.infrastructure.adapters.database.models.base import DatetimeTrackMixin
from museflow.infrastructure.adapters.database.models.base import UUIDIdMixin


class TasteProfileModel(UUIDIdMixin, DatetimeTrackMixin, Base, kw_only=True):
    __tablename__ = "museflow_taste_profile"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_museflow_taste_profile_user_name"),)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("museflow_user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    profile: Mapped[TasteProfileData] = mapped_column(JSONB, nullable=False)

    profiler_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
    )
    tracks_count: Mapped[int] = mapped_column(Integer, nullable=False)
    logic_version: Mapped[str] = mapped_column(String(32), nullable=False)

    status: Mapped[TasteProfileStatus] = mapped_column(
        Enum(TasteProfileStatus), nullable=False, server_default=TasteProfileStatus.FINISHED.name
    )
    checkpoint_profile: Mapped[TasteProfileData | None] = mapped_column(JSONB, nullable=True, default=None)
    checkpoint_batch_index: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)

    def to_entity(self) -> TasteProfileEntity:
        return TasteProfileEntity(
            id=self.id,
            name=self.name,
            user_id=self.user_id,
            profile=self.profile,
            profiler_metadata=self.profiler_metadata,
            tracks_count=self.tracks_count,
            logic_version=self.logic_version,
            status=self.status,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )


class TasteProfileBuildModel(UUIDIdMixin, Base, kw_only=True):
    """The lease of the build running on a profile, one per user and profile name.

    Apart from the profile: a build holds the name before its first checkpoint creates the profile row. A build killed
    without releasing its lease leaves an expired row, which the next build of the name takes over.
    """

    __tablename__ = "museflow_taste_profile_build"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_museflow_taste_profile_build_user_name"),)

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("museflow_user.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # The fencing token: each build draws its own, and writes only while the lease still holds it.
    build_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    lease_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
