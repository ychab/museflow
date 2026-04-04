# Step 2: Application Layer

**Part of:** [Master Plan](taste_profile_master_plan.md)
**Dependencies:** Step 1 (domain types + entity must exist)

> **Scope:** Ports + input schema only. The use case lives in Step 5 (after DB + Gemini adapter are in place).

## Files to touch

| Action | File |
|---|---|
| Create | `museflow/application/ports/advisors/taste.py` |
| Create | `museflow/application/ports/repositories/taste.py` |
| Create | `museflow/application/inputs/taste.py` |

## 1. Advisor port

```python
# museflow/application/ports/advisors/taste.py
from __future__ import annotations

from abc import ABC, abstractmethod

from museflow.domain.entities.music import Track
from museflow.domain.entities.taste import TasteProfileData


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
# museflow/application/ports/repositories/taste.py
from __future__ import annotations

import uuid
from abc import ABC, abstractmethod

from museflow.domain.entities.taste import UserTasteProfile
from museflow.domain.types import MusicAdvisor


class TasteProfileRepository(ABC):
    @abstractmethod
    async def upsert(self, profile: UserTasteProfile) -> UserTasteProfile: ...

    @abstractmethod
    async def get(self, user_id: uuid.UUID, advisor: MusicAdvisor) -> UserTasteProfile | None: ...
```

## 3. Input schema

```python
# museflow/application/inputs/taste.py
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class BuildTasteProfileConfigInput:
    track_limit: int = 3000
    batch_size: int = 400
```

## 4. `__init__.py` exports

Both `museflow/application/ports/advisors/__init__.py` and `museflow/application/ports/repositories/__init__.py` are intentionally left empty.

## Verification

```bash
make lint   # type check must pass
```

No tests in this step — use case + tests live in [Step 5](taste_profile_step_5_plan.md).
