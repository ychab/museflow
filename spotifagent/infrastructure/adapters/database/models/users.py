from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from spotifagent.infrastructure.adapters.database.models import Base
from spotifagent.infrastructure.adapters.database.models.base import DatetimeTrackMixin
from spotifagent.infrastructure.adapters.database.models.base import UUIDIdMixin

if TYPE_CHECKING:  # pragma: no cover
    from spotifagent.infrastructure.adapters.database.models import SpotifyAccount


class User(UUIDIdMixin, DatetimeTrackMixin, Base):
    __tablename__ = "spotifagent_user"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)

    is_active: Mapped[bool] = mapped_column(default=True)

    spotify_state: Mapped[str | None] = mapped_column(String(512), nullable=True, default=None)
    spotify_account: Mapped["SpotifyAccount | None"] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        init=False,
    )
