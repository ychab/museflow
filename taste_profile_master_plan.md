# Master Plan: Gemini Taste Profile (`muse profile build`)

## What this feature does

Sends a chronological slice of the user's library (~3,000 tracks) to Gemini in sequential batches of 400. Gemini builds a "Master Taste Profile" incrementally via a rolling merge strategy, then performs a final psychographic reflection. The profile is stored in the DB (one row per user+advisor, upserted on rebuild).

Complements — does not replace — the existing per-seed `get_similar_tracks()` advisor flow.

## CLI end state

```bash
muse profile build --email=user@example.com
muse profile build --email=user@example.com --track-limit=5000 --batch-size=300
```

Output: progress per batch + final summary (eras, personality archetype, life insights).

## Profile schema (stored as JSONB)

```python
class TasteEra(TypedDict):
    era_label: str                        # e.g. "The Post-Rock Exploration"
    time_range: str                       # e.g. "2021-2023"
    technical_fingerprint: dict[str, float]
    dominant_moods: list[str]

class TasteProfileData(TypedDict):
    taste_timeline: list[TasteEra]        # chronological map; merged/pruned during evolution
    core_identity: dict[str, float]       # stable DNA — foundation heavier in merges
    current_vibe: dict[str, float]        # recent trajectory — new segment heavier
    personality_archetype: str | None     # set by final psychographic pass
    life_phase_insights: list[str]        # set by final psychographic pass
```

## Key design decisions

| Decision | Choice | Reason |
|---|---|---|
| Profile storage | TypedDict as JSONB | Type-safe, no serialization headache |
| DB strategy | Upsert (replace) | One row per (user, profiler), simple |
| `built_at` field | Dropped | `updated_at` doubles as rebuild time |
| Resume on failure | No | Restart from scratch — upsert overwrites cleanly |
| Default batch size | 400 | Token efficiency (Gemini recommendation) |
| `logic_version` | Yes | Identifies stale profiles when prompts change |
| Psychographic pass | Yes | Final Gemini call populates `personality_archetype` + `life_phase_insights` |

## Gemini call sequence (per full run)

1. **`build_profile_segment(batch_1)`** → produces initial `TasteProfileData`
2. **`merge_profiles(foundation, segment_2..N)`** → evolves profile (era continuation or new era)
3. **`reflect_on_profile(final_profile)`** → populates `personality_archetype` + `life_phase_insights`

## Implementation steps

| Step | File | Status |
|---|---|---|
| [Step 1](taste_profile_step_1_plan.md) | Domain layer (types + entity) | ✅ Done |
| [Step 2](taste_profile_step_2_plan.md) | Application layer (ports + input schema) | ✅ Done |
| [Step 3](taste_profile_step_3_plan.md) | Infrastructure DB (model + repositories + migration) | ✅ Done |
| [Step 4](taste_profile_step_4_plan.md) | Gemini adapter (schemas + 3-prompt client) | ✅ Done |
| [Step 5](taste_profile_step_5_plan.md) | Use case + unit tests + integration tests (WireMock) | TODO |
| [Step 6](taste_profile_step_6_plan.md) | CLI + dependencies + exports | TODO |

## Verification (end-to-end)

1. `make db-revision && make db-upgrade` — verify `museflow_taste_profile` table
2. `muse profile build --email=...` — runs ~8 Gemini calls, stores profile
3. `SELECT profiler, tracks_count, logic_version, updated_at FROM museflow_taste_profile`
4. `make test` — 100% branch coverage
5. WireMock stubs needed: `tests/assets/wiremock/gemini/taste_profile_segment.json`, `taste_profile_merge.json`, `taste_profile_reflection.json`
