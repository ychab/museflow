# Step 4: Gemini Taste Profile Adapter

**Part of:** [Master Plan](taste_profile_master_plan.md)
**Dependencies:** Step 1 (types), Step 2 (port)

## Files to touch

| Action | File |
|---|---|
| Create | `museflow/infrastructure/adapters/advisors/gemini/taste_profile_schemas.py` |
| Create | `museflow/infrastructure/adapters/advisors/gemini/taste_profile_client.py` |

## Before starting — read these files

- `museflow/infrastructure/adapters/advisors/gemini/client.py` — retry decorator, `HttpClientMixin` usage, how `GeminiSettings` is injected
- `museflow/infrastructure/adapters/advisors/gemini/schemas.py` — `GeminiSchemaProperty`, `GeminiGenerationConfig`, `GeminiResponse` parsing pattern

## 1. `taste_profile_schemas.py`

Three `GeminiGenerationConfig` instances (one per prompt type), each with a `responseSchema` matching `TasteProfileData`.

```python
# Pydantic DTOs for parsing the inner JSON returned by Gemini

class GeminiTasteEra(BaseModel):
    era_label: str
    time_range: str
    technical_fingerprint: dict[str, float]
    dominant_moods: list[str]

class GeminiTasteProfileContent(BaseModel):
    taste_timeline: list[GeminiTasteEra]
    core_identity: dict[str, float]
    current_vibe: dict[str, float]
    personality_archetype: str | None = None
    life_phase_insights: list[str] = []
```

Build the `responseSchema` using `GeminiSchemaProperty` (existing builder):

```python
GEMINI_TASTE_PROFILE_RESPONSE_SCHEMA = GeminiSchemaProperty(
    type="object",
    properties={
        "taste_timeline": GeminiSchemaProperty(
            type="array",
            items=GeminiSchemaProperty(
                type="object",
                properties={
                    "era_label": GeminiSchemaProperty(type="string"),
                    "time_range": GeminiSchemaProperty(type="string"),
                    "technical_fingerprint": GeminiSchemaProperty(
                        type="object",
                        additional_properties=GeminiSchemaProperty(type="number"),
                    ),
                    "dominant_moods": GeminiSchemaProperty(
                        type="array", items=GeminiSchemaProperty(type="string")
                    ),
                },
            ),
        ),
        "core_identity": GeminiSchemaProperty(
            type="object", additional_properties=GeminiSchemaProperty(type="number")
        ),
        "current_vibe": GeminiSchemaProperty(
            type="object", additional_properties=GeminiSchemaProperty(type="number")
        ),
        "personality_archetype": GeminiSchemaProperty(type="string"),
        "life_phase_insights": GeminiSchemaProperty(
            type="array", items=GeminiSchemaProperty(type="string")
        ),
    },
)

GEMINI_TASTE_PROFILE_CONFIG = GeminiGenerationConfig(
    response_mime_type="application/json",
    response_schema=GEMINI_TASTE_PROFILE_RESPONSE_SCHEMA,
)
```

Note: all three calls (segment, merge, reflect) use the same `responseSchema` — reuse `GEMINI_TASTE_PROFILE_CONFIG`.

## 2. `taste_profile_client.py` — `GeminiTasteProfileAdapter`

MRO: `HttpClientMixin, TasteProfileAdvisorPort` (mixin first — matches existing pattern).

```python
class GeminiTasteProfileAdapter(HttpClientMixin, TasteProfileAdvisorPort):
    LOGIC_VERSION = "v1.0"

    def __init__(self, api_key: str, model: str, base_url: str, ...) -> None:
        HttpClientMixin.__init__(self, ...)

    @property
    def display_name(self) -> str:
        return "Gemini"

    @property
    def logic_version(self) -> str:
        return self.LOGIC_VERSION
```

### Track format helper

```python
def _format_tracks(tracks: list[Track]) -> str:
    lines = []
    for t in tracks:
        date_parts = []
        if t.added_at:
            date_parts.append(f"added:{t.added_at.date()}")
        if t.played_at:
            date_parts.append(f"last_played:{t.played_at.date()}")
        date_label = ", ".join(date_parts) if date_parts else "no_date"
        artists = " & ".join(a["name"] for a in t.artists)
        genres = ", ".join(t.genres) if t.genres else "unknown"
        lines.append(f"{date_label} | {artists} - {t.name} | genres: {genres}")
    return "\n".join(lines)
```

### Prompt 1 — `build_profile_segment`

```
Analyze these {N} tracks from [{date_range}]. Build a musical taste profile segment.
Return JSON with exactly these keys:
- "taste_timeline": one TasteEra for this batch
- "core_identity": {{genre_or_mood: weight 0-1}} long-term affinity signals
- "current_vibe": {{genre_or_mood: weight 0-1}} what this batch reveals right now
- "personality_archetype": null
- "life_phase_insights": []

Tracks:
{track_lines}
```

### Prompt 2 — `merge_profiles`

```
You are evolving a Master Taste Profile with new listening data.

Existing profile:
{foundation_json}

New segment:
{segment_json}

Rules:
- taste_timeline: decide if this segment continues the last era or starts a new one. Append or extend.
  Do not let it grow indefinitely — merge consecutive eras if very similar.
- core_identity: weighted blend, foundation heavier (long-term DNA, do not erase)
- current_vibe: new segment heavier (reflects recent pivots)
- personality_archetype: keep null (set by final pass)
- life_phase_insights: keep empty (set by final pass)

Return the same JSON structure.
```

### Prompt 3 — `reflect_on_profile`

```
You have the complete Master Taste Profile of a listener across their entire library.

Profile:
{profile_json}

Perform a final psychographic reflection. Populate:
- "personality_archetype": one evocative label (e.g. "The Architect of Sound")
- "life_phase_insights": list of observed life transitions
  (e.g. "Shift from high-energy industrial to calming ambient during 2024")

Return the full profile JSON with these two fields populated. Keep all other fields unchanged.
```

### Retry + HTTP pattern

Copy the `@retry` decorator and response-parsing pattern from `GeminiClientAdapter` exactly. Parse response text → validate with `GeminiTasteProfileContent` → cast to `TasteProfileData`.

### `close()`

```python
async def close(self) -> None:
    await self._http_client.aclose()
```

## Verification

```bash
make lint
```

WireMock stubs to create:
- `tests/assets/wiremock/gemini/taste_profile_segment.json`
- `tests/assets/wiremock/gemini/taste_profile_merge.json`
- `tests/assets/wiremock/gemini/taste_profile_reflection.json`

Unit tests:
- `tests/unit/infrastructure/advisors/gemini/test_taste_profile_client.py`
  - `test__build_profile_segment__nominal`
  - `test__merge_profiles__nominal`
  - `test__reflect_on_profile__nominal`
  - `test__retry_on_429`
