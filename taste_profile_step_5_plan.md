# Step 5: Use Case + Tests

**Part of:** [Master Plan](taste_profile_master_plan.md)
**Dependencies:** Steps 1–4 complete (entity, ports, DB model + repo, Gemini adapter all exist)

## Files to touch

| Action | File |
|---|---|
| Create | `museflow/application/use_cases/build_taste_profile.py` |
| Create | `tests/unit/application/use_cases/test_build_taste_profile.py` |
| Create | `tests/integration/application/use_cases/test_build_taste_profile.py` |
| Create | `tests/assets/wiremock/gemini/taste_profile_segment.json` |
| Create | `tests/assets/wiremock/gemini/taste_profile_merge.json` |
| Create | `tests/assets/wiremock/gemini/taste_profile_reflection.json` |

## 1. Use case

`museflow/application/use_cases/build_taste_profile.py`

```python
from __future__ import annotations

import itertools
import logging
import uuid
from datetime import UTC, datetime

from museflow.application.inputs.taste import BuildTasteProfileConfigInput
from museflow.application.ports.profilers.taste import TasteProfilerPort
from museflow.application.ports.repositories.music import TrackRepository
from museflow.application.ports.repositories.taste import TasteProfileRepository
from museflow.domain.entities.taste import TasteProfileData, TasteProfile
from museflow.domain.entities.user import User
from museflow.domain.exceptions import EmptyLibraryException  # or nearest equivalent
from museflow.domain.types import SortOrder, TasteProfiler, TrackOrderBy, TrackOrdering

logger = logging.getLogger(__name__)


class BuildTasteProfileUseCase:
    def __init__(
            self,
            track_repository: TrackRepository,
            profile_repository: TasteProfileRepository,
            profiler: TasteProfilerPort,
    ) -> None:
        self._track_repository = track_repository
        self._profile_repository = profile_repository
        self._profiler = profiler

    async def build_profile(
            self, user: User, config: BuildTasteProfileConfigInput
    ) -> TasteProfile:
        tracks = await self._track_repository.get_list(
            user_id=user.id,
            order=[(TrackOrderBy.PLAYED_AT, SortOrder.ASC), (TrackOrderBy.ADDED_AT, SortOrder.ASC)],
            limit=config.track_limit,
        )
        if not tracks:
            raise EmptyLibraryException(f"No tracks found for user {user.id}")

        current_profile: TasteProfileData | None = None

        for i, batch in enumerate(itertools.batched(tracks, config.batch_size)):
            segment = await self._profiler.build_profile_segment(list(batch))
            if current_profile is None:
                current_profile = segment
            else:
                current_profile = await self._profiler.merge_profiles(current_profile, segment)
            logger.info(
                f"Taste profile batch {i + 1} processed "
                f"({min((i + 1) * config.batch_size, len(tracks))} / {len(tracks)} tracks)"
            )

        assert current_profile is not None  # unreachable: tracks non-empty guarantees ≥1 iteration

        current_profile = await self._profiler.reflect_on_profile(current_profile)
        logger.info("Psychographic reflection complete")

        profile = TasteProfile(
            id=uuid.uuid4(),
            user_id=user.id,
            profiler=TasteProfiler.GEMINI,
            profile=current_profile,
            tracks_count=len(tracks),
            logic_version=self._profiler.logic_version,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        return await self._profile_repository.upsert(profile)
```

> `itertools.batched` requires Python 3.12+ (available on our 3.13 stack).
>
> `profiler=TasteProfiler.GEMINI` — hardcoded since `GeminiTasteProfileAdapter` is the only `TasteProfilerPort` impl for now.

## 2. Unit tests

`tests/unit/application/use_cases/test_build_taste_profile.py`

- **nominal — multiple batches**: 3 batches → `build_profile_segment` called 3×, `merge_profiles` called 2×, `reflect_on_profile` called 1×, `upsert` called 1×
- **single batch**: `build_profile_segment` called 1×, `merge_profiles` never called, `reflect_on_profile` called 1×
- **empty tracks**: `get_list` returns `[]` → raises `EmptyLibraryException`

Use `AsyncMock` for all ports.

## 3. Integration tests

`tests/integration/application/use_cases/test_build_taste_profile.py`

- **nominal**: real DB + WireMock Gemini stubs → profile row created in `museflow_user_taste_profile`
- **upsert**: run twice → still 1 row, `updated_at` changes, `tracks_count` updated
- **empty library**: no tracks in DB for user → raises `EmptyLibraryException`

Use `async_session_trans` (explicit commit path via `upsert`).

## 4. WireMock stubs

Three stub files under `tests/assets/wiremock/gemini/`:

- `taste_profile_segment.json` — stub for `build_profile_segment` prompt → returns a `TasteProfileData` JSON
- `taste_profile_merge.json` — stub for `merge_profiles` prompt → returns merged `TasteProfileData` JSON
- `taste_profile_reflection.json` — stub for `reflect_on_profile` prompt → returns profile with `personality_archetype` + `life_phase_insights` filled

Pattern follows existing Spotify/Last.fm stubs in `tests/assets/wiremock/`.

## Verification

```bash
make lint
make test
```
