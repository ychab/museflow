import uuid
from typing import NotRequired
from typing import TypedDict

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

from museflow.domain.entities.music import Album
from museflow.domain.entities.music import Artist as ArtistEntity
from museflow.domain.entities.music import Track as TrackEntity
from museflow.domain.entities.music import TrackArtist
from museflow.domain.types import AlbumType
from museflow.domain.types import MusicProvider
from museflow.infrastructure.adapters.database.models.base import Base
from museflow.infrastructure.adapters.database.models.base import DatetimeTrackMixin
from museflow.infrastructure.adapters.database.models.base import UUIDIdMixin


class ArtistDict(TypedDict):
    provider_id: str
    name: str


class AlbumDict(TypedDict):
    provider_id: str
    name: str
    album_type: NotRequired[str]


class MusicItemMixin(UUIDIdMixin, DatetimeTrackMixin, MappedAsDataclass, kw_only=True):
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("museflow_user.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        sort_order=-50,
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    popularity: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)

    is_saved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_top: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    top_position: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)

    genres: Mapped[list[str]] = mapped_column(
        ARRAY(String),
        nullable=False,
        default_factory=list,
        sort_order=300,
    )

    provider: Mapped[MusicProvider] = mapped_column(Enum(MusicProvider), nullable=False, sort_order=990)
    provider_id: Mapped[str] = mapped_column(String(512), nullable=False, sort_order=991)

    @declared_attr
    def __table_args__(cls):
        return (UniqueConstraint("user_id", "provider_id", name=f"uq_{cls.__tablename__}_user_provider_id"),)


class Artist(MusicItemMixin, Base):
    __tablename__ = "museflow_artist"

    def to_entity(self) -> ArtistEntity:
        return ArtistEntity(
            id=self.id,
            provider=self.provider,
            user_id=self.user_id,
            provider_id=self.provider_id,
            name=self.name,
            popularity=self.popularity,
            is_saved=self.is_saved,
            is_top=self.is_top,
            top_position=self.top_position,
            genres=self.genres,
        )


class Track(MusicItemMixin, Base, kw_only=True):
    __tablename__ = "museflow_track"

    artists: Mapped[list[ArtistDict]] = mapped_column(JSONB, nullable=False, default_factory=list)
    album: Mapped[AlbumDict | None] = mapped_column(JSONB, nullable=True, default=None)

    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)

    isrc: Mapped[str | None] = mapped_column(String(512), nullable=True, default=None, index=True)
    fingerprint: Mapped[str] = mapped_column(String(512), nullable=False, index=True)

    @staticmethod
    def _to_album_entity(album_dict: AlbumDict) -> Album:
        return Album(
            provider_id=album_dict["provider_id"],
            name=album_dict["name"],
            album_type=AlbumType(album_dict["album_type"]) if album_dict.get("album_type") else None,
        )

    def to_entity(self) -> TrackEntity:
        return TrackEntity(
            id=self.id,
            provider=self.provider,
            user_id=self.user_id,
            provider_id=self.provider_id,
            name=self.name,
            popularity=self.popularity,
            is_saved=self.is_saved,
            is_top=self.is_top,
            top_position=self.top_position,
            artists=[TrackArtist(provider_id=artist["provider_id"], name=artist["name"]) for artist in self.artists],
            genres=self.genres,
            album=self._to_album_entity(self.album) if self.album else None,
            duration_ms=self.duration_ms,
            isrc=self.isrc,
            fingerprint=self.fingerprint,
        )
