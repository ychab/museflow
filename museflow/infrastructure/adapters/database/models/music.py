import uuid
from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy import Enum
from sqlalchemy import ForeignKey
from sqlalchemy import Index
from sqlalchemy import String
from sqlalchemy import UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from museflow.domain.entities.music import Track as TrackEntity
from museflow.domain.types import MusicProvider
from museflow.infrastructure.adapters.database.models.base import Base
from museflow.infrastructure.adapters.database.models.base import DatetimeTrackMixin
from museflow.infrastructure.adapters.database.models.base import UUIDIdMixin


class Track(UUIDIdMixin, DatetimeTrackMixin, Base, kw_only=True):
    __tablename__ = "museflow_track"

    __table_args__ = (
        UniqueConstraint("user_id", "provider_id", name="uq_museflow_track_user_provider_id"),
        Index("ix_museflow_track_user_provider", "user_id", "provider"),
        Index("ix_museflow_track_user_fingerprint", "user_id", "fingerprint"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("museflow_user.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        sort_order=-50,
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)

    provider: Mapped[MusicProvider] = mapped_column(Enum(MusicProvider), nullable=False, sort_order=990)
    provider_id: Mapped[str] = mapped_column(String(512), nullable=False, sort_order=991)

    artists: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default_factory=list)
    album_name: Mapped[str | None] = mapped_column(String(512), nullable=True, default=None)

    fingerprint: Mapped[str] = mapped_column(String(512), nullable=False, index=True)

    played_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)

    def to_entity(self) -> TrackEntity:
        return TrackEntity(
            id=self.id,
            provider=self.provider,
            user_id=self.user_id,
            provider_id=self.provider_id,
            name=self.name,
            artists=self.artists,
            album_name=self.album_name,
            fingerprint=self.fingerprint,
            played_at=self.played_at,
        )
