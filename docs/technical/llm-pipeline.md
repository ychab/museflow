# LLM pipeline

Four components use a language model or its output, and each sits behind a port so the use cases never see a vendor, a prompt or a JSON payload:

| Component | Port | Where | Job |
|---|---|---|---|
| Profiler | `TasteProfilerPort` | `adapters/profilers/openrouter/` | Condense a listening history into a structured taste profile |
| Advisor | `AdvisorPort` | `adapters/advisors/openrouter/` | Propose tracks the user does not know, guided by the profile |
| Reconciler | none (domain service) | `domain/services/reconciler.py` | Match free-text suggestions to real catalogue tracks |
| Enricher | `TrackEnricherPort` | `adapters/enrichers/openrouter/` | Tag tracks with genres, moods and language |

A design stance runs through all of them: **the model proposes, deterministic code disposes.** Output is constrained by a JSON response schema, validated by Pydantic, restricted to closed vocabularies, matched against the real catalogue, and filtered against what the user already knows or has blacklisted. The model never writes to the database or to the provider directly.

## Gateway: OpenRouter

Every LLM call goes through [OpenRouter](https://openrouter.ai), an OpenAI-compatible gateway in front of many model vendors. The three adapters share one `OpenRouterClient` ([`common/llm/client.py`](https://github.com/ychab/museflow/blob/main/museflow/infrastructure/adapters/common/llm/client.py)), built by composition, which owns the HTTP envelope, the retries and the reply parsing. An adapter only holds its prompts, its response schema and the settings of its steps.

Each request carries:

- **A strict JSON schema** (`response_format: json_schema`, `strict: true`), built with `JsonSchemaProperty` ([`common/llm/json_schema.py`](https://github.com/ychab/museflow/blob/main/museflow/infrastructure/adapters/common/llm/json_schema.py)): `additionalProperties: false` on every object, every property required, optional values expressed as nullable types. Strict mode forbids free-form keys, so the profile's `{tag: weight}` maps travel as lists of `{key, value}` pairs, one list per vocabulary tier (`genre_macro`, `genre_meso`, `genre_micro`, `mood`); the merge and reflect prompts embed the profile in that same shape, so the model reads what it must write back.
- **Provider preferences**: `require_parameters: true`, so OpenRouter only routes to endpoints that support structured outputs and every tuning parameter the step sends; `zdr: true` (Zero Data Retention, `OPENROUTER_ZDR`, on by default) and `data_collection: deny`, see [Privacy and data](privacy-and-data.md).
- **Fallback models**, tried in order by OpenRouter when the main model fails. The model that actually answered is logged at DEBUG.

**Fail fast on a misconfigured model.** Before any paid call, each command checks its step models (and their fallbacks) against OpenRouter's public model catalog: an unknown id fails with a "Did you mean" suggestion, and a model that lacks a parameter the step sends (structured outputs, reasoning, temperature, max tokens) fails with the missing list. With ZDR on, it also reads the public list of Zero Data Retention endpoints (`GET /endpoints/zdr`): a model with no ZDR endpoint, or whose ZDR endpoints lack one of those parameters, fails before any paid call too. Without that check, OpenRouter only refuses it on the first completion, with a 404 "No endpoints found matching your data policy". The check remains a necessary condition: OpenRouter picks the endpoint at request time.

## Portable response schemas

Any step can run on any model, so a response schema must be accepted by every provider behind OpenRouter, not only by the default one. Provider rejections taught three rules, which `JsonSchemaProperty` enforces and a unit test (`test_schema_portability.py`) checks on every real schema:

- **An enum holds at most 100 values.** Gemini rejects a larger one with a bare `400 INVALID_ARGUMENT`. A larger vocabulary is split across fields, which is why genres travel as one field (or one weight list) per tier.
- **`anyOf` does not get around the limit:** Gemini adds up the values of every branch.
- **A nullable enum is `anyOf [enum, null]`.** The OpenAI shape, `type: ["string", "null"]` with an `enum`, is rejected by Anthropic.

The live suite (`tests/integration/live/openrouter`) sends the real schemas to a few model families before a release.

## Model choice per step

Each step has its own `LLMSettings` ([`museflow/infrastructure/config/settings/openrouter.py`](https://github.com/ychab/museflow/blob/main/museflow/infrastructure/config/settings/openrouter.py)): `MODEL`, `MAX_TOKENS`, `REASONING_EFFORT`, `TEMPERATURE` and `FALLBACK_MODELS`. Only the model has a default; the others are left to the provider. A field is overridden with a nested environment variable, and the step keeps its other defaults:

```bash
OPENROUTER_ENRICHER__MODEL=openai/gpt-5-nano
OPENROUTER_PROFILER_REFLECT__REASONING_EFFORT=high
OPENROUTER_ADVISOR__FALLBACK_MODELS=["anthropic/claude-sonnet-4.5"]
```

The CLI also overrides the model for one run: `enrich tracks --model`, `taste build --segment-model / --merge-model / --reflect-model`, `playlist discover --model`. Current defaults:

| Step | Setting | Default model | Volume | Why this tier |
|---|---|---|---|---|
| Profile segment | `PROFILER_SEGMENT` | `google/gemini-3.1-flash-lite` | One call per batch (15 for the default 3,000 seeds in batches of 200) | High volume, narrow task: classify a batch of tracks into tags and weights against a closed vocabulary. A small, cheap model is enough |
| Profile merge | `PROFILER_MERGE` | `google/gemini-3.5-flash` | One call per batch after the first | Needs to follow arithmetic and structural rules over a growing JSON document without drifting. A step up from the lite tier |
| Profile reflect | `PROFILER_REFLECT` | `google/gemini-3.1-pro-preview` | **One call per build** | The only step that writes narrative and judgement (archetype, life-phase insights, behavioural traits). Run once, so the most capable model is affordable |
| Advisor | `ADVISOR` | `google/gemini-3.5-flash` | Up to `--max-attempts` calls per playlist (default 3) | Needs musical knowledge and instruction-following, called interactively |
| Enricher | `ENRICHER` | `google/gemini-3.1-flash-lite` | One call per batch of 200 tracks | Pure classification into closed vocabularies, repeated over the whole library |

The principle is to spend model capability where one call has outsized influence on the result (the single reflection pass, the merge that every later step builds on) and use the cheapest tier where the work is high-volume and constrained. The defaults stay on Gemini, as before the gateway, but on 3.x models: the 2.5 Flash and Flash Lite models MuseFlow used have no Zero Data Retention endpoint, so ZDR routing refuses them. They were not benchmarked against other vendors, so treat the tiering as a reasoned default, not a measured optimum. Comparing models is now a `--model` flag away.

!!! note "Reasoning tokens count against `MAX_TOKENS`"
    On reasoning models, the hidden reasoning is billed and counted as output tokens. A low `MAX_TOKENS` can cut the JSON off (`finish_reason: length`), which fails the call as truncated. The defaults leave `MAX_TOKENS` unset for that reason.

## Profiler: batches, merge, reflect

```mermaid
flowchart TD
    A["Seed tracks: most played first, limit 3000 by default"] --> B["Re-sort chronologically by last played"]
    B --> C["Split into batches (200 by default)"]
    C --> D{"Resume and checkpoint exists?"}
    D -- yes --> E["Load partial profile, skip finished batches"]
    D -- no --> F["Batch 1"]
    E --> F
    F --> G["Segment: batch to partial profile (lite model)"]
    G --> H{"First batch?"}
    H -- yes --> I["Partial profile becomes the foundation"]
    H -- no --> J["Merge: foundation + segment (mid model)"]
    I --> K["Save checkpoint, status BUILDING"]
    J --> K
    K --> L{"More batches?"}
    L -- yes --> M["Optional throttle sleep"] --> G
    L -- no --> N["Reflect: add archetype and traits (pro model)"]
    N --> O["Sort timeline, upsert, status FINISHED, clear checkpoint"]
    G -. rate limit or invalid reply .-> P["Raise TasteProfileBuildPaused, run again with --resume"]
    J -. rate limit or invalid reply .-> P
    N -. rate limit or invalid reply .-> P
```

Source: [`taste_profile_build.py`](https://github.com/ychab/museflow/blob/main/museflow/application/use_cases/taste_profile_build.py) (orchestration) and [`profilers/openrouter/client.py`](https://github.com/ychab/museflow/blob/main/museflow/infrastructure/adapters/profilers/openrouter/client.py) (prompts).

Design decisions:

- **Map, then fold, then reflect.** A 3,000-track history does not fit comfortably in one prompt and a single huge prompt is fragile. Each batch is summarised independently (segment), then folded into a running profile (merge). The final reflection sees only the profile, never raw tracks.
- **Chronological batches.** Seeds are selected by play count (best signal) and then re-sorted by last-played date, so each batch covers a coherent period and the model can describe it as a "taste era" with a time range.
- **Merge rules are explicit in the prompt**, not left to the model: if a new segment is more than 80% similar to the last era it extends that era's end date, otherwise it adds an era; the timeline is capped at 15 eras by merging the oldest; `core_identity` is a weighted average (foundation 0.7, segment 0.3); `current_vibe` is replaced wholesale. The weights encode a product opinion: long-term identity moves slowly, current mood does not.
- **User ratings are part of the signal.** Each track line carries first / last played, play count and, if rated, the score. The prompt tells the model to treat high scores as confirmed anchors and minimum scores as anti-preferences.
- **Checkpoint and pause.** After every batch the partial profile and batch index are persisted ([Data model](data-model.md#taste-profile)). A rate-limit overrun or an unusable reply raises `TasteProfileBuildPausedException` instead of losing the run; `taste build --resume` continues from the next batch. `TASTE_PROFILE_BUILD_THROTTLING_SLEEP_SECONDS` can space out batches to stay under a quota.
- **The reflect step is resumable.** The reflection result itself is not checkpointed, but the merged profile is saved after the last batch. A rate-limit overrun or unusable reply in the final call also raises `TasteProfileBuildPausedException` (reported as batch N/N), and `--resume` skips every batch and repeats only that final call.
- **Reproducibility metadata.** `logic_version` (currently `v2.0`) and, in `profiler_metadata`, the gateway and the settings of each step (model, fallbacks, reasoning effort, max tokens, temperature) are stored with the profile.

## Advisor: guided discovery

`get_discovery_strategy` returns a `DiscoveryTasteStrategy`: a reasoning paragraph, a strategy label, a list of recommended tracks each with a confidence score, 2 to 3 free-text search queries, and a playlist name. The prompt is assembled in [`advisors/openrouter/client.py`](https://github.com/ychab/museflow/blob/main/museflow/infrastructure/adapters/advisors/openrouter/client.py), as a system message (the role and rules) and a user message (the session's focus and hints), from:

| Input | Source | Purpose |
|---|---|---|
| Profile summaries | Archetype, core identity, current vibe, behavioural traits and era timeline rendered by pure helpers in `domain/utils/taste.py` | Who the listener is |
| Risk calibration | Derived from the `openness` and `adventurousness` traits: both below 0.4 means stay in the comfort zone, either above 0.7 means push into adjacent territory | How far to stray |
| Focus strategy | `expansion`, `roots_revival` or `cultural_bridge`; the last two interpolate the oldest and current era labels from the profile | What kind of discovery |
| Genre and mood hints, custom instructions | Optional CLI flags | Per-session steering |
| Exclusion list | Everything suggested in earlier attempts of the same run | Avoid repeats across attempts |
| Blacklist | Blacklisted artists and tracks | Hard "never suggest" |
| Liked tracks | Tracks rated 7 or more, at most 200 | Concrete taste anchors beyond statistics |

**Quality over quantity** is stated in the prompt: only return a track if confidence would be at least 0.7, and return fewer than the requested limit rather than pad. This is an instruction to the model, not a post-filter in code; the confidence values are used afterwards for ranking. The strategy response is constrained by a strict JSON schema and validated into Pydantic models.

## Reconciler: from suggestion to catalogue track

An LLM suggests *names*; the provider needs *ids*. For each suggestion the use case searches the provider (`--reconciler-limit` candidates) and asks the `Reconciler` to pick the best candidate:

1. Normalise suggestion and candidate (`normalize_text`: ASCII fold, lowercase, strip feature / remaster / live suffixes).
2. Score the track name with `token_sort_ratio` and the artist with `WRatio` (RapidFuzz).
3. If either component is below `RECONCILER_MATCH_THRESHOLD` (80), the candidate scores 0.
4. Otherwise the composite is `0.6 * track + 0.4 * artist`. A candidate scoring 0 is never accepted, so scores are either 0 or between the threshold and 100. The best non-zero candidate is accepted and its score divided by 100 becomes the **match confidence**.

Two scores therefore travel with each track: the advisor's confidence ("is this a good pick for the listener?") and the reconciler's confidence ("is this the track the advisor meant?"). The final order uses both: advisor score rounded down to a band of 0.05, then match confidence inside the band, so a marginally higher advisor score cannot outrank a clearly more certain catalogue match. A per-artist cap (`--max-tracks-per-artist`, default 3) is applied after sorting so one artist cannot dominate a playlist.

Fuzzy matching is deliberately a domain service: it is pure, deterministic and cheap to test with table-driven cases, and it is the guard against the most visible LLM failure mode, a plausible-sounding track that does not exist.

## Enricher: closed vocabularies

Given title and primary artist (nothing else), the enricher returns 2 to 3 genres ordered macro to micro, 1 to 2 moods, and the list of 2-letter language codes of the *lyrics* (`locales`, several when the lyrics mix languages, empty for an instrumental or when no signal is reliable) (the prompt explicitly separates lyrics language from artist nationality and lists script and title-vocabulary signals). The prompt lists the allowed values for each field, and the response schema constrains genres and moods to those values with enums. Genres come back as one field per tier (`genre_macro`, `genre_meso`, and `genre_micro`, which may be null), recombined into the track's ordered list, because a single enum of all 166 genres is larger than some providers accept; the response is validated and then **unknown values are dropped** rather than rejected: genres and moods not in `GenreTag` / `MoodTag` are filtered out, and a locale code that is not two letters is dropped from `locales` (duplicates are removed); if every returned code is invalid, `locales` stays `NULL` so the track remains eligible. A track is never written with an empty genres or moods list: the use case skips that field and logs a warning, so the track stays eligible. Dropping keeps a batch usable when the model invents one tag, at the cost of occasionally storing a shorter list. The field set is selectable (`genre`, `mood`, `locale`; the last one fills `locales`) and `--force` re-enriches already-tagged tracks, which is how a taxonomy change is rolled out. The profiler applies the same restriction to the profile: identity keys outside the vocabulary are removed during validation, and mood values are filtered per era.

## Resilience

Three independent layers, each handling a different failure class:

| Failure | Layer | Behaviour |
|---|---|---|
| Network error, HTTP 408, 429, 5xx | `tenacity` `@retry` on `OpenRouterClient.make_api_call` | Exponential backoff (2 s to 60 s), at most `OPENROUTER_HTTP_MAX_RETRIES` (10) attempts. A 429 with a `Retry-After` header within `OPENROUTER_HTTP_MAX_RETRY_WAIT` (120 s) sleeps that long; a longer wait aborts with `LLMRateLimitError`, which the advisor and profiler turn into their domain `RateLimitExceeded`. The cap prevents a command from silently sleeping for hours. A predicate, `_is_retryable_error`, explicitly returns `False` for everything else, so it propagates instead of looping |
| Request rejected (400, 401, 402, 503 "no provider") | `LLMRequestError` | Not retried: a bad key, missing credits or routing rules no endpoint satisfies will not fix themselves. 503 is excluded from the retries for that reason. The error carries OpenRouter's own message |
| Structurally invalid reply (bad JSON, schema violation) | `@self_heal` | Re-sends the conversation extended with the model's bad answer and the validation error, asking for corrected JSON |
| Unusable reply (no choices, provider error in a 200, refusal, truncated, empty) | `parse_completion` | Fails fast with a typed `LLMResponseError` (`no_choices`, `provider_error`, `refused`, `truncated`, `empty_response`); not retried, because showing the model its own error cannot fix them |

`RateLimitRetry` is a plain exception, not tenacity's `TryAgain`, because tenacity 9.2 unwraps an exhausted `TryAgain` into its cause, which would bypass the conversion to the domain exception (documented in [`http.py`](https://github.com/ychab/museflow/blob/main/museflow/infrastructure/adapters/http.py)).

### Self-healing structured output

```python
@self_heal()
async def complete[T: BaseModel](self, messages, /, *, response_model, schema, llm, adapter) -> T:
    ...
    return parse_completion(response_data, response_model, adapter)
```

`parse_completion` turns the raw HTTP body into the response model or raises `LLMResponseError` with a failure kind. `@self_heal` ([source](https://github.com/ychab/museflow/blob/main/museflow/infrastructure/adapters/common/llm/self_heal.py)) wraps the call: on a self-healable failure it appends two turns to the conversation, the model's own invalid text (role `assistant`) and a user message `Your previous response is invalid: <detail>. Return only the corrected JSON conforming to the schema.`, and calls again, for at most `OPENROUTER_VALIDATION_MAX_RETRIES` extra attempts (default 2, so up to 3 calls). Exhaustion logs an error and re-raises. A recovery logs a warning so the rate of invalid replies stays observable. With strict schemas enforced by the provider, these failures should become rare; the logs will tell whether the decorator still earns its place.

It is a decorator, in the spirit of tenacity's `@retry`, so it can be removed with no other change, and it sits on the one method the three adapters share. It was introduced in commit `a8ad2dc`, on the Gemini adapters, and moved to the OpenRouter client unchanged.

Failure surfaces differ by component, on purpose: the advisor and profiler translate a final failure into a domain exception (`DiscoveryTasteStrategyException`, `TasteProfileBuildException`) that the CLI reports or turns into a pause; the enricher sorts its failures by scope, because it runs over the whole library and every failed batch may still be billed:

- **Fatal for the run**: the request is refused for a reason every batch shares (401 invalid key, 402 no credits, 404 unknown model, 5xx or 503 no provider, network down after the retries, rate limit over the cap). The adapter raises `EnricherUnavailableException` or `EnricherRateLimitExceeded`, and the use case stops at once.
- **Failed batch**: a rejection that may depend on the batch content (400, 403 moderation, 413, 422), or an unusable reply. The use case logs it and moves on.
- **Circuit breaker**: after `max_consecutive_failures` failed batches in a row (3, in `EnrichTracksConfigInput`), the use case stops anyway. This caps the cost of a systematic failure nobody foresaw, such as a `MAX_TOKENS` too low truncating every reply, to three paid calls. A successful batch resets the count.

Either stop raises `TrackEnrichmentAbortedException` with the batch reached and the tracks enriched so far. Every batch enriched before the stop is already saved, so a re-run picks up the tracks still missing a field.
