import uuid

from sqlalchemy import Enum
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from museflow.domain.entities.playlist import Playlist as PlaylistEntity
from museflow.domain.types import DiscoveryFocus
from museflow.domain.types import MusicProvider
from museflow.domain.types import PlaylistType
from museflow.infrastructure.adapters.database.models.base import Base
from museflow.infrastructure.adapters.database.models.base import DatetimeTrackMixin
from museflow.infrastructure.adapters.database.models.base import UUIDIdMixin


class Playlist(UUIDIdMixin, DatetimeTrackMixin, Base, kw_only=True):
    __tablename__ = "museflow_playlist"

    # Identity / FK
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("museflow_user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        sort_order=-50,
    )

    # Provider
    provider: Mapped[MusicProvider] = mapped_column(Enum(MusicProvider), nullable=False, sort_order=-48)
    provider_id: Mapped[str] = mapped_column(String(512), nullable=False, sort_order=-47)
    snapshot_id: Mapped[str | None] = mapped_column(String(512), nullable=True, default=None, sort_order=-46)

    # Content
    type: Mapped[PlaylistType] = mapped_column(Enum(PlaylistType), nullable=False)
    name: Mapped[str] = mapped_column(String(512), nullable=False)

    # Discovery-specific — nullable, only set for type == PlaylistType.DISCOVERY
    profile_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("museflow_taste_profile.id", ondelete="CASCADE"),
        nullable=True,
        default=None,
    )
    reasoning: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    focus: Mapped[DiscoveryFocus | None] = mapped_column(Enum(DiscoveryFocus), nullable=True, default=None)
    genre: Mapped[str | None] = mapped_column(String(255), nullable=True, default=None)
    mood: Mapped[str | None] = mapped_column(String(255), nullable=True, default=None)
    custom_instructions: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)

    @classmethod
    def from_entity(cls, entity: PlaylistEntity) -> "Playlist":
        return cls(
            id=entity.id,
            user_id=entity.user_id,
            provider=entity.provider,
            provider_id=entity.provider_id,
            snapshot_id=entity.snapshot_id,
            type=entity.type,
            name=entity.name,
            profile_id=entity.profile_id,
            reasoning=entity.reasoning,
            focus=entity.focus,
            genre=entity.genre,
            mood=entity.mood,
            custom_instructions=entity.custom_instructions,
        )

    def to_entity(self) -> PlaylistEntity:
        return PlaylistEntity(
            id=self.id,
            user_id=self.user_id,
            provider=self.provider,
            provider_id=self.provider_id,
            snapshot_id=self.snapshot_id,
            type=self.type,
            name=self.name,
            profile_id=self.profile_id,
            reasoning=self.reasoning,
            focus=self.focus,
            genre=self.genre,
            mood=self.mood,
            custom_instructions=self.custom_instructions,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )


class PlaylistTrack(UUIDIdMixin, Base, kw_only=True):
    """Join table linking playlists to tracks in museflow_track."""

    __tablename__ = "museflow_playlist_track"

    playlist_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("museflow_playlist.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        sort_order=-50,
    )
    track_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("museflow_track.id", ondelete="CASCADE"),
        nullable=False,
        sort_order=-49,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, sort_order=-48)
