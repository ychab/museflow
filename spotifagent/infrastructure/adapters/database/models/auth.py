import uuid

from sqlalchemy import Enum
from sqlalchemy import ForeignKey
from sqlalchemy import String
from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from spotifagent.domain.entities.music import MusicProvider
from spotifagent.infrastructure.adapters.database.models.base import Base
from spotifagent.infrastructure.adapters.database.models.base import DatetimeTrackMixin
from spotifagent.infrastructure.adapters.database.models.base import NumericIdMixin


class AuthProviderState(NumericIdMixin, DatetimeTrackMixin, Base, kw_only=True):
    __tablename__ = "spotifagent_auth_provider_state"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("spotifagent_user.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider: Mapped[MusicProvider] = mapped_column(Enum(MusicProvider), nullable=False)

    state: Mapped[str] = mapped_column(String(512), nullable=False, index=True, unique=True)

    __table_args__ = (UniqueConstraint("user_id", "provider", name="uq_user_provider_pending_auth"),)
