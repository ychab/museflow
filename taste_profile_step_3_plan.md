# Step 3: Infrastructure — Database

**Part of:** [Master Plan](taste_profile_master_plan.md)
**Dependencies:** Step 1 (entity), Step 2 (repository port + `get_for_profile` abstract method)

## Files to touch

| Action | File |
|---|---|
| Create | `museflow/infrastructure/adapters/database/models/taste_profile.py` |
| Modify | `museflow/infrastructure/adapters/database/models/__init__.py` (if exists, or the models import location) |
| Create | `museflow/infrastructure/adapters/database/repositories/taste_profile.py` |
| Modify | `museflow/infrastructure/adapters/database/repositories/music.py` |
| Run | `make db-revision` then `make db-upgrade` |

## 1. SQLAlchemy model

Read `museflow/infrastructure/adapters/database/models/base.py` first to confirm mixin names (`UUIDIdMixin`, `DatetimeTrackMixin`).

```python
# museflow/infrastructure/adapters/database/models/taste_profile.py
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from museflow.domain.entities.taste_profile import UserTasteProfile as UserTasteProfileEntity
from museflow.domain.types import TasteProfileData
from museflow.infrastructure.adapters.database.models.base import Base, DatetimeTrackMixin, UUIDIdMixin


class UserTasteProfileModel(UUIDIdMixin, DatetimeTrackMixin, Base, kw_only=True):
    __tablename__ = "museflow_user_taste_profile"
    __table_args__ = (
        UniqueConstraint("user_id", "advisor", name="uq_museflow_user_taste_profile_user_advisor"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("museflow_user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        sort_order=-50,
    )
    advisor: Mapped[str] = mapped_column(String(64), nullable=False, sort_order=-49)
    profile: Mapped[TasteProfileData] = mapped_column(JSONB, nullable=False, sort_order=-48)
    tracks_count: Mapped[int] = mapped_column(Integer, nullable=False, sort_order=-47)
    logic_version: Mapped[str] = mapped_column(String(32), nullable=False, sort_order=-46)

    def to_entity(self) -> UserTasteProfileEntity:
        return UserTasteProfileEntity(
            id=self.id,
            user_id=self.user_id,
            advisor=self.advisor,
            profile=self.profile,
            tracks_count=self.tracks_count,
            logic_version=self.logic_version,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )
```

**Important:** `id`, `created_at`, `updated_at` come from mixins with `init=False`. Do NOT redeclare them.

## 2. SQL repository

Read `museflow/infrastructure/adapters/database/repositories/music.py` for upsert patterns (`pg_insert`, `.returning()`).

```python
# museflow/infrastructure/adapters/database/repositories/taste_profile.py
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from museflow.application.ports.repositories.taste_profile import UserTasteProfileRepository
from museflow.domain.entities.taste_profile import UserTasteProfile
from museflow.infrastructure.adapters.database.models.taste_profile import UserTasteProfileModel


class UserTasteProfileSQLRepository(UserTasteProfileRepository):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert(self, profile: UserTasteProfile) -> UserTasteProfile:
        stmt = (
            pg_insert(UserTasteProfileModel)
            .values(
                id=profile.id,
                user_id=profile.user_id,
                advisor=profile.advisor,
                profile=profile.profile,
                tracks_count=profile.tracks_count,
                logic_version=profile.logic_version,
            )
            .on_conflict_do_update(
                constraint="uq_museflow_user_taste_profile_user_advisor",
                set_={
                    "profile": pg_insert(UserTasteProfileModel).excluded.profile,
                    "tracks_count": pg_insert(UserTasteProfileModel).excluded.tracks_count,
                    "logic_version": pg_insert(UserTasteProfileModel).excluded.logic_version,
                    "updated_at": func.now(),
                },
            )
            .returning(UserTasteProfileModel)
        )
        result = await self.session.execute(stmt)
        profile_db = result.scalar_one()
        await self.session.commit()
        return profile_db.to_entity()

    async def get_by_user_and_advisor(
        self, user_id: uuid.UUID, advisor: str
    ) -> UserTasteProfile | None:
        stmt = select(UserTasteProfileModel).where(
            UserTasteProfileModel.user_id == user_id,
            UserTasteProfileModel.advisor == advisor,
        )
        result = await self.session.execute(stmt)
        profile_db = result.scalar_one_or_none()
        return profile_db.to_entity() if profile_db else None
```

Note: import `func` from `sqlalchemy` for `func.now()`.

## 3. Implement `get_for_profile()` in music repository

Open `museflow/infrastructure/adapters/database/repositories/music.py`, find `TrackSQLRepository`, add:

```python
async def get_for_profile(self, user: User, limit: int, offset: int = 0) -> list[Track]:
    stmt = (
        select(TrackModel)
        .where(TrackModel.user_id == user.id)
        .order_by(func.coalesce(TrackModel.played_at, TrackModel.added_at).asc().nullslast())
        .limit(limit)
        .offset(offset)
    )
    result = await self.session.execute(stmt)
    return [row.to_entity() for row in result.scalars().all()]
```

## 4. Migration

Make sure the model is imported in the Alembic env (check `env.py` or the models `__init__`). Then:

```bash
make db-revision   # generates a new migration file
# Review the generated migration to confirm it creates museflow_user_taste_profile
make db-upgrade
```

## Verification

```bash
make db-upgrade
# Check table exists:
# psql -c "\d museflow_user_taste_profile"
make test   # integration tests for the new repo + get_for_profile
```

Integration tests to write:
- `tests/integration/application/use_cases/test_build_taste_profile.py` (after Step 4/5)
- `tests/integration/infrastructure/repositories/test_taste_profile_repository.py`
  - `test__upsert__creates_new`
  - `test__upsert__replaces_existing` (same user+advisor, different profile)
  - `test__get_by_user_and_advisor__found`
  - `test__get_by_user_and_advisor__not_found`
- Add branch for `get_for_profile` in existing music repo tests
