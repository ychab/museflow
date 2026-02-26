from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from museflow.domain.entities.user import User as UserEntity
from museflow.infrastructure.adapters.database.models import Base
from museflow.infrastructure.adapters.database.models.base import DatetimeTrackMixin
from museflow.infrastructure.adapters.database.models.base import UUIDIdMixin


class User(UUIDIdMixin, DatetimeTrackMixin, Base):
    __tablename__ = "museflow_user"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)

    is_active: Mapped[bool] = mapped_column(default=True)

    def to_entity(self) -> UserEntity:
        return UserEntity(
            id=self.id,
            email=self.email,
            hashed_password=self.hashed_password,
            is_active=self.is_active,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )
