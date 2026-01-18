import uuid
from typing import Any

from sqlalchemy import ARRAY
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


class TopMusicMixin(UUIDIdMixin, DatetimeTrackMixin, MappedAsDataclass, kw_only=True):
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("spotifagent_user.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    popularity: Mapped[int] = mapped_column(Integer, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    provider: Mapped[MusicProvider] = mapped_column(Enum(MusicProvider), nullable=False, sort_order=990)
    provider_id: Mapped[str] = mapped_column(String(512), nullable=False, sort_order=991)

    @declared_attr
    def __table_args__(cls):
        return (UniqueConstraint("user_id", "provider_id", name=f"uq_{cls.__tablename__}_user_provider_id"),)


class TopArtist(TopMusicMixin, Base, kw_only=True):
    __tablename__ = "spotifagent_music_top_artist"

    genres: Mapped[list[str]] = mapped_column(
        ARRAY(String),
        nullable=False,
        default_factory=list,
        sort_order=50,
    )


class TopTrack(TopMusicMixin, Base, kw_only=True):
    __tablename__ = "spotifagent_music_top_track"

    artists: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=False,
        default_factory=list,
        sort_order=50,
    )
