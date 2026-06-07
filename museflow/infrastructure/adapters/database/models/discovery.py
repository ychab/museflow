import uuid

from sqlalchemy import Enum
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from museflow.domain.entities.discovery import DiscoveryPlaylist as DiscoveryPlaylistEntity
from museflow.domain.types import DiscoveryFocus
from museflow.domain.types import MusicProvider
from museflow.infrastructure.adapters.database.models.base import Base
from museflow.infrastructure.adapters.database.models.base import DatetimeTrackMixin
from museflow.infrastructure.adapters.database.models.base import UUIDIdMixin


class DiscoveryPlaylist(UUIDIdMixin, DatetimeTrackMixin, Base, kw_only=True):
    __tablename__ = "museflow_discovery_playlist"

    # Identity / FK
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("museflow_user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        sort_order=-50,
    )
    profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("museflow_taste_profile.id", ondelete="CASCADE"),
        nullable=False,
        sort_order=-49,
    )

    # Provider
    provider: Mapped[MusicProvider] = mapped_column(Enum(MusicProvider), nullable=False, sort_order=-48)
    provider_id: Mapped[str] = mapped_column(String(512), nullable=False, sort_order=-47)

    # Content
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    reasoning: Mapped[str] = mapped_column(Text, nullable=False)
    focus: Mapped[DiscoveryFocus] = mapped_column(Enum(DiscoveryFocus), nullable=False)
    genre: Mapped[str | None] = mapped_column(String(255), nullable=True, default=None)
    mood: Mapped[str | None] = mapped_column(String(255), nullable=True, default=None)
    custom_instructions: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)

    @classmethod
    def from_entity(cls, entity: DiscoveryPlaylistEntity) -> "DiscoveryPlaylist":
        return cls(
            id=entity.id,
            user_id=entity.user_id,
            profile_id=entity.profile_id,
            provider=entity.provider,
            provider_id=entity.provider_id,
            name=entity.name,
            reasoning=entity.reasoning,
            focus=entity.focus,
            genre=entity.genre,
            mood=entity.mood,
            custom_instructions=entity.custom_instructions,
        )

    def to_entity(self) -> DiscoveryPlaylistEntity:
        return DiscoveryPlaylistEntity(
            id=self.id,
            user_id=self.user_id,
            profile_id=self.profile_id,
            provider=self.provider,
            provider_id=self.provider_id,
            name=self.name,
            reasoning=self.reasoning,
            focus=self.focus,
            genre=self.genre,
            mood=self.mood,
            custom_instructions=self.custom_instructions,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )


class DiscoveryPlaylistTrack(UUIDIdMixin, Base, kw_only=True):
    """Join table linking discovery playlists to tracks in museflow_track."""

    __tablename__ = "museflow_discovery_playlist_track"

    playlist_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("museflow_discovery_playlist.id", ondelete="CASCADE"),
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
