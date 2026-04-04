# Step 2: Application Layer

**Part of:** [Master Plan](taste_profile_master_plan.md)
**Dependencies:** Step 1 (domain types + entity must exist)

## Files to touch

| Action | File |
|---|---|
| Create | `museflow/application/ports/advisors/taste_profile.py` |
| Modify | `museflow/application/ports/advisors/__init__.py` |
| Create | `museflow/application/ports/repositories/taste_profile.py` |
| Modify | `museflow/application/ports/repositories/__init__.py` |
| Modify | `museflow/application/ports/repositories/music.py` |
| Create | `museflow/application/inputs/taste_profile.py` |
| Create | `museflow/application/use_cases/build_taste_profile.py` |

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

## 5. Use case

```python
# museflow/application/use_cases/build_taste_profile.py
from __future__ import annotations

import itertools
import logging
import uuid
from datetime import UTC, datetime

from museflow.application.inputs.taste_profile import BuildTasteProfileConfigInput
from museflow.application.ports.advisors.taste_profile import TasteProfileAdvisorPort
from museflow.application.ports.repositories.music import TrackRepository
from museflow.application.ports.repositories.taste_profile import UserTasteProfileRepository
from museflow.domain.entities.taste_profile import UserTasteProfile
from museflow.domain.entities.user import User
from museflow.domain.types import TasteProfileData

logger = logging.getLogger(__name__)


class BuildTasteProfileUseCase:
    def __init__(
        self,
        track_repository: TrackRepository,
        profile_repository: UserTasteProfileRepository,
        advisor: TasteProfileAdvisorPort,
    ) -> None:
        self._track_repository = track_repository
        self._profile_repository = profile_repository
        self._advisor = advisor

    async def build_profile(
        self, user: User, config: BuildTasteProfileConfigInput
    ) -> UserTasteProfile:
        tracks = await self._track_repository.get_for_profile(user, limit=config.track_limit)
        current_profile: TasteProfileData | None = None

        for i, batch in enumerate(itertools.batched(tracks, config.batch_size)):
            segment = await self._advisor.build_profile_segment(list(batch))
            if current_profile is None:
                current_profile = segment
            else:
                current_profile = await self._advisor.merge_profiles(current_profile, segment)
            logger.info(
                f"Taste profile batch {i + 1} processed ({min((i + 1) * config.batch_size, len(tracks))} / {len(tracks)} tracks)"
            )

        assert current_profile is not None  # guaranteed: tracks list is non-empty

        current_profile = await self._advisor.reflect_on_profile(current_profile)
        logger.info("Psychographic reflection complete")

        profile = UserTasteProfile(
            id=uuid.uuid4(),
            user_id=user.id,
            advisor=self._advisor.display_name,
            profile=current_profile,
            tracks_count=len(tracks),
            logic_version=self._advisor.logic_version,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        return await self._profile_repository.upsert(profile)
```

Note: uses `itertools.batched` (Python 3.12+, available in our Python 3.13 stack).

## 6. `__init__.py` exports

- `museflow/application/ports/advisors/__init__.py` — add `TasteProfileAdvisorPort`
- `museflow/application/ports/repositories/__init__.py` — add `UserTasteProfileRepository`

## Verification

```bash
make lint   # type check must pass
```

Unit tests for the use case:
- `tests/unit/application/use_cases/test_build_taste_profile.py`
- Test: nominal path (multiple batches + reflect call)
- Test: single-batch path (no merge call)
- Test: empty tracks raises / handled (decide behavior)
