import uuid
from datetime import UTC
from datetime import datetime

from sqlalchemy import UUID
from sqlalchemy import DateTime
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import MappedAsDataclass
from sqlalchemy.orm import mapped_column


class Base(MappedAsDataclass, AsyncAttrs, DeclarativeBase, kw_only=True):
    pass


class DatetimeTrackMixin(MappedAsDataclass, kw_only=True):
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default_factory=lambda: datetime.now(UTC),
        nullable=False,
        sort_order=998,
        init=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        default_factory=lambda: datetime.now(UTC),
        nullable=False,
        sort_order=999,
        init=False,
    )


class NumericIdMixin(MappedAsDataclass, kw_only=True):
    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
        sort_order=-100,
        init=False,
    )


class UUIDIdMixin(MappedAsDataclass, kw_only=True):
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default_factory=uuid.uuid4,
        sort_order=-100,
    )
