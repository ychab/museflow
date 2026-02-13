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

from spotifagent.domain.entities.music import MusicProvider
from spotifagent.infrastructure.adapters.database.models.base import Base
from spotifagent.infrastructure.adapters.database.models.base import DatetimeTrackMixin
from spotifagent.infrastructure.adapters.database.models.base import UUIDIdMixin


class UserProviderMixin(UUIDIdMixin, DatetimeTrackMixin, MappedAsDataclass, kw_only=True):
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("spotifagent_user.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        sort_order=-50,
    )

    provider: Mapped[MusicProvider] = mapped_column(Enum(MusicProvider), nullable=False, sort_order=990)
    provider_id: Mapped[str] = mapped_column(String(512), nullable=False, sort_order=991)

    @declared_attr
    def __table_args__(cls):
        return (UniqueConstraint("user_id", "provider_id", name=f"uq_{cls.__tablename__}_user_provider_id"),)


class MusicItemMixin(UserProviderMixin, MappedAsDataclass, kw_only=True):
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)

    popularity: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)

    is_saved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    is_top: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    top_position: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)


class Artist(MusicItemMixin, Base):
    __tablename__ = "spotifagent_music_artist"

    genres: Mapped[list[str]] = mapped_column(
        ARRAY(String),
        nullable=False,
        default_factory=list,
        sort_order=50,
    )


class Track(MusicItemMixin, Base):
    __tablename__ = "spotifagent_music_track"

    artists: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=False,
        default_factory=list,
        sort_order=50,
    )
