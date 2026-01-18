import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from spotifagent.infrastructure.adapters.database.models.base import Base
from spotifagent.infrastructure.adapters.database.models.base import NumericIdMixin

if TYPE_CHECKING:  # pragma: no cover
    from spotifagent.infrastructure.adapters.database.models import User


class SpotifyAccount(NumericIdMixin, Base, kw_only=True):
    __tablename__ = "spotify_account"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("spotifagent_user.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    user: Mapped["User"] = relationship(back_populates="spotify_account", init=False)

    token_type: Mapped[str] = mapped_column(String(512), nullable=False)
    token_access: Mapped[str] = mapped_column(String(512), nullable=False)
    token_refresh: Mapped[str] = mapped_column(String(512), nullable=False)
    token_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
