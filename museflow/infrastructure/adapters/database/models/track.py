import uuid
from datetime import datetime
from typing import TypedDict

from sqlalchemy import Boolean
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from museflow.domain.entities.track import ProviderLink
from museflow.domain.entities.track import Track as TrackEntity
from museflow.domain.types import GenreTag
from museflow.domain.types import LocaleCode
from museflow.domain.types import MoodTag
from museflow.domain.types import MusicProvider
from museflow.domain.types import TrackSource
from museflow.infrastructure.adapters.database.models.base import Base
from museflow.infrastructure.adapters.database.models.base import DatetimeTrackMixin
from museflow.infrastructure.adapters.database.models.base import UUIDIdMixin


class ProviderLinkDict(TypedDict):
    provider: str  # MusicProvider str value
    provider_id: str


class Track(UUIDIdMixin, DatetimeTrackMixin, Base, kw_only=True):
    __tablename__ = "museflow_track"

    __table_args__ = (UniqueConstraint("user_id", "fingerprint", name="uq_museflow_track_user_fingerprint"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("museflow_user.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        sort_order=-50,
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)

    provider_links: Mapped[list[ProviderLinkDict]] = mapped_column(JSONB, nullable=False, default_factory=list)

    artists: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default_factory=list)
    album_name: Mapped[str | None] = mapped_column(String(512), nullable=True, default=None)

    fingerprint: Mapped[str] = mapped_column(String(512), nullable=False, index=True)

    played_at_first: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)
    played_at_last: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)
    played_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    source: Mapped[int] = mapped_column(Integer, nullable=False, default=int(TrackSource.HISTORY))
    score: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    score_skipped: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

    genres: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default_factory=list)
    moods: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default_factory=list)
    locale: Mapped[LocaleCode | None] = mapped_column(String(10), nullable=True, default=None)

    @classmethod
    def from_entity(cls, entity: TrackEntity) -> "Track":
        return cls(
            id=entity.id,
            user_id=entity.user_id,
            name=entity.name,
            provider_links=[
                {"provider": link.provider.value, "provider_id": link.provider_id} for link in entity.provider_links
            ],
            artists=entity.artists,
            album_name=entity.album_name,
            fingerprint=entity.fingerprint,
            played_at_first=entity.played_at_first,
            played_at_last=entity.played_at_last,
            played_count=entity.played_count,
            source=int(entity.source),
            score=entity.score,
            score_skipped=entity.score_skipped,
            genres=[g.value for g in entity.genres],
            moods=[m.value for m in entity.moods],
            locale=entity.locale,
        )

    def to_entity(self) -> TrackEntity:
        return TrackEntity(
            id=self.id,
            user_id=self.user_id,
            name=self.name,
            provider_links=[
                ProviderLink(provider=MusicProvider(link["provider"]), provider_id=link["provider_id"])
                for link in self.provider_links
            ],
            artists=self.artists,
            album_name=self.album_name,
            fingerprint=self.fingerprint,
            played_at_first=self.played_at_first,
            played_at_last=self.played_at_last,
            played_count=self.played_count,
            source=TrackSource(self.source),
            score=self.score,
            score_skipped=self.score_skipped,
            genres=[GenreTag(g) for g in self.genres],
            moods=[MoodTag(m) for m in self.moods],
            locale=self.locale,
        )
