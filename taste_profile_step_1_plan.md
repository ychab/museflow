# Step 1: Domain Layer

**Part of:** [Master Plan](taste_profile_master_plan.md)
**Dependencies:** None — start here.

## Files to touch

| Action | File |
|---|---|
| Modify | `museflow/domain/types.py` |
| Create | `museflow/domain/entities/taste.py` |
| Modify | `museflow/domain/entities/__init__.py` |

## 1. `museflow/domain/types.py` — add TypedDicts

Read the file first to find the right place to insert (after existing TypedDicts/enums).

```python
class TasteEra(TypedDict):
    era_label: str                           # AI-generated name, e.g. "The Post-Rock Exploration"
    time_range: str                          # e.g. "2021-2023"
    technical_fingerprint: dict[str, float]  # BPM, reverb, energy (0-1 weights)
    dominant_moods: list[str]

class TasteProfileData(TypedDict):
    taste_timeline: list[TasteEra]           # chronological map of taste eras
    core_identity: dict[str, float]          # stable DNA, e.g. {"progressive metal": 0.8}
    current_vibe: dict[str, float]           # active trajectory (last ~400 tracks)
    personality_archetype: str | None        # e.g. "The Architect of Sound" — set by final pass
    life_phase_insights: list[str]           # e.g. ["Shift to ambient during 2024"] — set by final pass
```

## 2. `museflow/domain/entities/taste.py` — new entity

Pattern: frozen dataclass, kw_only, no framework imports. Declare all fields explicitly (no base class for `id`/`created_at`/`updated_at`).

```python
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from museflow.domain.types import TasteProfileData


@dataclass(frozen=True, kw_only=True)
class TasteProfile:
    id: uuid.UUID
    user_id: uuid.UUID
    advisor: str              # e.g. "Gemini"
    profile: TasteProfileData
    tracks_count: int
    logic_version: str        # e.g. "v1.0" — bump when prompts change
    created_at: datetime
    updated_at: datetime      # doubles as built_at
```

## 3. `museflow/domain/entities/__init__.py` — export

Add `TasteProfile` to the existing exports.

## Verification

```bash
make lint   # should pass with no new errors
```

No tests needed at this step alone — the entity is a pure dataclass with no logic.
