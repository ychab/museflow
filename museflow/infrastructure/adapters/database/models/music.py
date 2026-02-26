import uuid
from typing import Any

from sqlalchemy import ARRAY
from sqlalchemy import Boolean
from sqlalchemy import Enum
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import MappedAsDataclass
from sqlalchemy.orm import declared_attr
from sqlalchemy.orm import mapped_column

from museflow.domain.entities.music import Artist as ArtistEntity
from museflow.domain.entities.music import Track as TrackEntity
from museflow.domain.entities.music import TrackArtist
from museflow.domain.types import MusicProvider
from museflow.infrastructure.adapters.database.models.base import Base
from museflow.infrastructure.adapters.database.models.base import DatetimeTrackMixin
from museflow.infrastructure.adapters.database.models.base import UUIDIdMixin


class MusicItemMixin(UUIDIdMixin, DatetimeTrackMixin, MappedAsDataclass, kw_only=True):
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("museflow_user.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        sort_order=-50,
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    popularity: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)

    is_saved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_top: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    top_position: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)

    provider: Mapped[MusicProvider] = mapped_column(Enum(MusicProvider), nullable=False, sort_order=990)
    provider_id: Mapped[str] = mapped_column(String(512), nullable=False, sort_order=991)

    @declared_attr
    def __table_args__(cls):
        return (UniqueConstraint("user_id", "provider_id", name=f"uq_{cls.__tablename__}_user_provider_id"),)


class Artist(MusicItemMixin, Base):
    __tablename__ = "museflow_artist"

    genres: Mapped[list[str]] = mapped_column(
        ARRAY(String),
        nullable=False,
        default_factory=list,
        sort_order=50,
    )

    def to_entity(self) -> ArtistEntity:
        return ArtistEntity(
            id=self.id,
            provider=self.provider,
            user_id=self.user_id,
            provider_id=self.provider_id,
            name=self.name,
            slug=self.slug,
            popularity=self.popularity,
            is_saved=self.is_saved,
            is_top=self.is_top,
            top_position=self.top_position,
            genres=self.genres,
        )


class Track(MusicItemMixin, Base):
    __tablename__ = "museflow_track"

    artists: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=False,
        default_factory=list,
        sort_order=50,
    )

    def to_entity(self) -> TrackEntity:
        return TrackEntity(
            id=self.id,
            provider=self.provider,
            user_id=self.user_id,
            provider_id=self.provider_id,
            name=self.name,
            slug=self.slug,
            popularity=self.popularity,
            is_saved=self.is_saved,
            is_top=self.is_top,
            top_position=self.top_position,
            artists=[TrackArtist(provider_id=artist["provider_id"], name=artist["name"]) for artist in self.artists],
        )
