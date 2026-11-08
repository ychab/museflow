import uuid
from datetime import datetime
from typing import TYPE_CHECKING
from typing import TypedDict

from sqlalchemy import Boolean
from sqlalchemy import ColumnElement
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import ScalarSelect
from sqlalchemy import String
from sqlalchemy import UniqueConstraint
from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import column_property
from sqlalchemy.orm import mapped_column

from museflow.domain.entities.track import ProviderLink
from museflow.domain.entities.track import Track as TrackEntity
from museflow.domain.enums import GenreTag
from museflow.domain.enums import MoodTag
from museflow.domain.enums import MusicProvider
from museflow.domain.enums import TrackSource
from museflow.domain.value_objects.track import TrackPlay as TrackPlayEntity
from museflow.infrastructure.adapters.database.models.base import Base
from museflow.infrastructure.adapters.database.models.base import DatetimeTrackMixin
from museflow.infrastructure.adapters.database.models.base import NumericIdMixin
from museflow.infrastructure.adapters.database.models.base import UUIDIdMixin


class ProviderLinkDict(TypedDict):
    provider: str  # MusicProvider str value
    provider_id: str


class TrackPlay(NumericIdMixin, Base, kw_only=True):
    """One listen of a track: the only source of a track's play data."""

    __tablename__ = "museflow_track_play"

    # Also the index of the per-track aggregates: count, first and last play.
    __table_args__ = (UniqueConstraint("track_id", "played_at", name="uq_museflow_track_play_track_played_at"),)

    track_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("museflow_track.id", ondelete="CASCADE"),
        nullable=False,
        sort_order=-50,
    )
    played_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    @classmethod
    def from_entity(cls, entity: TrackPlayEntity) -> TrackPlay:
        return cls(track_id=entity.track_id, played_at=entity.played_at)

    def to_entity(self) -> TrackPlayEntity:
        return TrackPlayEntity(track_id=self.track_id, played_at=self.played_at)


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

    source: Mapped[int] = mapped_column(Integer, nullable=False, default=int(TrackSource.HISTORY))
    score: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    score_skipped: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

    genres: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default_factory=list)
    moods: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default_factory=list)
    locales: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True, default=None)

    if TYPE_CHECKING:  # pragma: no cover
        # Computed from the plays and mapped after the class, below: read like columns, never written.
        played_at_first: Mapped[datetime | None] = mapped_column(init=False)
        played_at_last: Mapped[datetime | None] = mapped_column(init=False)
        played_count: Mapped[int] = mapped_column(init=False)

    @classmethod
    def from_entity(cls, entity: TrackEntity) -> Track:
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
            source=int(entity.source),
            score=entity.score,
            score_skipped=entity.score_skipped,
            genres=[g.value for g in entity.genres],
            moods=[m.value for m in entity.moods],
            locales=entity.locales,
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
            locales=self.locales,
        )


# The play data of a track is computed from its plays at every load, so it never drifts from them: `to_entity`, the
# filters and the ordering read these like columns. Mapped after the class, as the subqueries need its own `id`.
def _plays_aggregate[T](aggregate: ColumnElement[T]) -> ScalarSelect[T]:
    return select(aggregate).where(TrackPlay.track_id == Track.id).correlate_except(TrackPlay).scalar_subquery()


Track.played_at_first = column_property(_plays_aggregate(func.min(TrackPlay.played_at)))
Track.played_at_last = column_property(_plays_aggregate(func.max(TrackPlay.played_at)))
Track.played_count = column_property(_plays_aggregate(func.count(TrackPlay.id)))
