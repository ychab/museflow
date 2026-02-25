import uuid
from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy import Enum
from sqlalchemy import ForeignKey
from sqlalchemy import String
from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from museflow.domain.entities.music import MusicProvider
from museflow.infrastructure.adapters.database.models.base import Base
from museflow.infrastructure.adapters.database.models.base import DatetimeTrackMixin
from museflow.infrastructure.adapters.database.models.base import NumericIdMixin


class AuthProviderState(NumericIdMixin, DatetimeTrackMixin, Base, kw_only=True):
    __tablename__ = "museflow_auth_provider_state"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("museflow_user.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider: Mapped[MusicProvider] = mapped_column(Enum(MusicProvider), nullable=False)

    state: Mapped[str] = mapped_column(String(512), nullable=False, index=True, unique=True)

    __table_args__ = (UniqueConstraint("user_id", "provider", name="uq_user_provider_auth_state"),)


class AuthProviderToken(NumericIdMixin, Base, kw_only=True):
    __tablename__ = "museflow_auth_provider_token"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("museflow_user.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider: Mapped[MusicProvider] = mapped_column(Enum(MusicProvider), nullable=False)

    token_type: Mapped[str] = mapped_column(String(512), nullable=False)
    token_access: Mapped[str] = mapped_column(String(512), nullable=False)
    token_refresh: Mapped[str] = mapped_column(String(512), nullable=False)
    token_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (UniqueConstraint("user_id", "provider", name="uq_user_provider_auth_token"),)
