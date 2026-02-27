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
    """Base class for all SQLAlchemy declarative models in the application.

    This class combines:
      - `MappedAsDataclass` for dataclass-like behavior
      - `AsyncAttrs` for asynchronous attribute access
      - `DeclarativeBase` to enable declarative mapping of Python classes to database tables.
    """

    pass


class DatetimeTrackMixin(MappedAsDataclass, kw_only=True):
    """A mixin for SQLAlchemy models to automatically track creation and update timestamps.

    Models inheriting from this mixin will automatically have `created_at` and
    `updated_at` fields, which are managed by the database (server_default)
    and updated on each modification.
    """

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
    """A mixin for SQLAlchemy models that provides an auto-incrementing integer primary key.

    Models inheriting from this mixin will have an `id` field that is an
    auto-incrementing integer, suitable for simple primary keys.
    """

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
        sort_order=-100,
        init=False,
    )


class UUIDIdMixin(MappedAsDataclass, kw_only=True):
    """A mixin for SQLAlchemy models that provides a UUID primary key.

    Models inheriting from this mixin will have an `id` field that is a
    UUID, automatically generated upon creation, providing globally unique identifiers.
    """

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default_factory=uuid.uuid4,
        sort_order=-100,
    )
