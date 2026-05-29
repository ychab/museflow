import uuid

from sqlalchemy import ForeignKey
from sqlalchemy import String
from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from museflow.domain.entities.blacklist import BlacklistedArtist as BlacklistedArtistEntity
from museflow.domain.entities.blacklist import BlacklistedTrack as BlacklistedTrackEntity
from museflow.infrastructure.adapters.database.models.base import Base
from museflow.infrastructure.adapters.database.models.base import DatetimeTrackMixin
from museflow.infrastructure.adapters.database.models.base import UUIDIdMixin


class BlacklistedArtist(UUIDIdMixin, DatetimeTrackMixin, Base, kw_only=True):
    __tablename__ = "museflow_blacklisted_artist"
    __table_args__ = (UniqueConstraint("user_id", "fingerprint", name="uq_museflow_blacklisted_artist_user_fp"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("museflow_user.id", ondelete="CASCADE"),
        nullable=False,
        sort_order=-50,
    )
    artist_name: Mapped[str] = mapped_column(String(512), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(512), nullable=False)

    def to_entity(self) -> BlacklistedArtistEntity:
        return BlacklistedArtistEntity(
            id=self.id,
            user_id=self.user_id,
            artist_name=self.artist_name,
            fingerprint=self.fingerprint,
            created_at=self.created_at,
        )


class BlacklistedTrack(UUIDIdMixin, DatetimeTrackMixin, Base, kw_only=True):
    __tablename__ = "museflow_blacklisted_track"
    __table_args__ = (UniqueConstraint("user_id", "fingerprint", name="uq_museflow_blacklisted_track_user_fp"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("museflow_user.id", ondelete="CASCADE"),
        nullable=False,
        sort_order=-50,
    )
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    artist_name: Mapped[str] = mapped_column(String(512), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(512), nullable=False)

    def to_entity(self) -> BlacklistedTrackEntity:
        return BlacklistedTrackEntity(
            id=self.id,
            user_id=self.user_id,
            name=self.name,
            artist_name=self.artist_name,
            fingerprint=self.fingerprint,
            created_at=self.created_at,
        )
