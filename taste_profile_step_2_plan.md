# Step 2: Application Layer

**Part of:** [Master Plan](taste_profile_master_plan.md)
**Dependencies:** Step 1 (domain types + entity must exist)

> **Scope:** Ports + input schema only. The use case lives in Step 5 (after DB + Gemini adapter are in place).

## Files to touch

| Action | File |
|---|---|
| Create | `museflow/application/ports/advisors/taste_profile.py` |
| Modify | `museflow/application/ports/advisors/__init__.py` |
| Create | `museflow/application/ports/repositories/taste_profile.py` |
| Modify | `museflow/application/ports/repositories/__init__.py` |
| Modify | `museflow/application/ports/repositories/music.py` |
| Create | `museflow/application/inputs/taste_profile.py` |
## 1. Advisor port

```python
# museflow/application/ports/advisors/taste_profile.py
from __future__ import annotations

from abc import ABC, abstractmethod

from museflow.domain.entities.music import Track
from museflow.domain.types import TasteProfileData


class TasteProfileAdvisorPort(ABC):
    @property
    @abstractmethod
    def display_name(self) -> str: ...

    @property
    @abstractmethod
    def logic_version(self) -> str: ...

    @abstractmethod
    async def build_profile_segment(self, tracks: list[Track]) -> TasteProfileData:
        """Analyze a batch of tracks and return a partial taste profile."""

    @abstractmethod
    async def merge_profiles(
        self, foundation: TasteProfileData, new_segment: TasteProfileData
    ) -> TasteProfileData:
        """Merge new_segment into the existing foundation profile."""

    @abstractmethod
    async def reflect_on_profile(self, profile: TasteProfileData) -> TasteProfileData:
        """Final psychographic pass: populate personality_archetype and life_phase_insights."""

    @abstractmethod
    async def close(self) -> None: ...
```

## 2. Repository port

```python
# museflow/application/ports/repositories/taste_profile.py
from __future__ import annotations

import uuid
from abc import ABC, abstractmethod

from museflow.domain.entities.taste_profile import UserTasteProfile


class UserTasteProfileRepository(ABC):
    @abstractmethod
    async def upsert(self, profile: UserTasteProfile) -> UserTasteProfile: ...

    @abstractmethod
    async def get_by_user_and_advisor(
        self, user_id: uuid.UUID, advisor: str
    ) -> UserTasteProfile | None: ...
```

## 3. Extend `TrackRepository` in `music.py`

Add the abstract method to the existing `TrackRepository` ABC:

```python
@abstractmethod
async def get_for_profile(self, user: User, limit: int, offset: int = 0) -> list[Track]:
    """Return tracks ordered by COALESCE(played_at, added_at) ASC NULLS LAST."""
```

## 4. Input schema

```python
# museflow/application/inputs/taste_profile.py
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class BuildTasteProfileConfigInput:
    track_limit: int = 3000
    batch_size: int = 400
```

## 5. `__init__.py` exports

- `museflow/application/ports/advisors/__init__.py` — add `TasteProfileAdvisorPort`
- `museflow/application/ports/repositories/__init__.py` — add `UserTasteProfileRepository`

## Verification

```bash
make lint   # type check must pass
```

No tests in this step — use case + tests live in [Step 5](taste_profile_step_5_plan.md).
