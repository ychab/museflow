import uuid

from sqlalchemy import Enum
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from museflow.domain.entities.taste import TasteProfileData
from museflow.domain.entities.taste import UserTasteProfile as TasteProfileEntity
from museflow.domain.types import MusicAdvisor
from museflow.infrastructure.adapters.database.models.base import Base
from museflow.infrastructure.adapters.database.models.base import DatetimeTrackMixin
from museflow.infrastructure.adapters.database.models.base import UUIDIdMixin


class TasteProfileModel(UUIDIdMixin, DatetimeTrackMixin, Base, kw_only=True):
    __tablename__ = "museflow_taste_profile"
    __table_args__ = (UniqueConstraint("user_id", "advisor", name="uq_museflow_taste_profile_user_advisor"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("museflow_user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    advisor: Mapped[MusicAdvisor] = mapped_column(Enum(MusicAdvisor), nullable=False)
    profile: Mapped[TasteProfileData] = mapped_column(JSONB, nullable=False)
    tracks_count: Mapped[int] = mapped_column(Integer, nullable=False)
    logic_version: Mapped[str] = mapped_column(String(32), nullable=False)

    def to_entity(self) -> TasteProfileEntity:
        return TasteProfileEntity(
            id=self.id,
            user_id=self.user_id,
            advisor=self.advisor,
            profile=self.profile,
            tracks_count=self.tracks_count,
            logic_version=self.logic_version,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )
