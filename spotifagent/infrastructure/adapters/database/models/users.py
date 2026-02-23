from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from spotifagent.infrastructure.adapters.database.models import Base
from spotifagent.infrastructure.adapters.database.models.base import DatetimeTrackMixin
from spotifagent.infrastructure.adapters.database.models.base import UUIDIdMixin


class User(UUIDIdMixin, DatetimeTrackMixin, Base):
    __tablename__ = "spotifagent_user"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)

    is_active: Mapped[bool] = mapped_column(default=True)
