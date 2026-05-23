# MuseFlow V2 — Strategic Plan

## Why V2

V1 proved the concept: sync your Spotify library, build a taste profile, discover similar music. It was a complete and valuable learning exercise — OAuth flows, Spotify API pagination, Last.fm similarity, clean hexagonal architecture, async SQLAlchemy, the works. V1 will remain on its branch, archived with pride.

But V1's core problem is that it bets on Spotify's API remaining generous and stable. It doesn't. Spotify is restricting third-party API access aggressively. And the recommendation quality — 95% of generated tracks end up discarded — reveals that more API data doesn't translate to better music discovery.

V2 bets on AI instead. The insight: the user's listening **history** is richer signal than any real-time API sync, it's fully private, and it belongs to the user. Feed that history to a capable language model, build a deep taste profile, and use AI to generate high-confidence recommendations. No library sync. No real-time metadata fetching. Just the user's data and a smart model.

---

## V2 Vision

**Three pillars:**

```
Import  →  Profile  →  Discover
```

1. **Import** — ingest listening history from any provider's export file (JSON, CSV). Privacy-first: the user exports their data and gives it to MuseFlow. No OAuth required for import.

2. **Profile** — build a rich, persistent AI taste portrait from that history. The profile captures listening eras, core musical DNA, behavioral traits, and what the user actively dislikes. This is the central artifact of the system — everything else serves it.

3. **Discover** — generate curated, high-confidence playlists based on the profile. Deliver them to the user's platform of choice. The AI knows what the user loves and what to avoid.

---

## What Gets Dropped from V1

### Last.fm adapter
Only consumer was `discover_similar`. Unmaintained API, limited to historical data. Gemini covers this use case better.

### `discover_similar` use case
Redundant with `discover_taste`. Creates confusion. Removed entirely.

### `provider_sync_library` use case
Fetches top artists, top/saved/playlist tracks from Spotify. High API call count, fragile dependency, no longer needed once history import is the primary data source.

### `Artist` entity + DB table
Artists were populated by library sync. Once sync is gone, artists become orphaned metadata. Artist information is already embedded in `Track.artists[]` (a JSONB field). The standalone entity can be removed progressively.

### Top/saved/playlist track source flags on `Track`
`Track.sources` included `TOP`, `SAVED`, `PLAYLIST` — all from library sync. Remaining valid sources: `HISTORY`.

### Spotify OAuth scopes for reading
OAuth will still exist for playlist output (writing), but read scopes (`user-top-read`, `user-library-read`, etc.) can be dropped.

---

## What Stays (Slimmed)

### Spotify: output-only
Narrowed to:
- OAuth + token management (needed for playlist write)
- Track search (resolve "Artist — Track Name" → Spotify URI for playlist creation)
- Playlist create/update

~2 API calls per discovery session. No library scans.

### `import_streaming_history` use case
Unchanged. The cleanest data pipeline in the codebase. Future: add more provider adapters behind the same port.

### `build_taste_profile` use case + Gemini profiler
Core of V2. Enhanced (see Profile Enhancement epic below).

### `discover_taste` use case
Core of V2. Enhanced (see Discovery Quality epic below). The only discovery path.

### Gemini advisor adapter
Kept. Prompting and context will be enriched.

---

## Epics

Each epic below is a self-contained chunk of work, ordered by dependency. Each one can be split into a smaller implementation plan following the standard layer order:

```
1. domain (entities, value objects, exceptions)
2. application ports (ABCs)
3. infrastructure adapters (port implementations)
4. use cases + input schemas
5. entrypoints (CLI commands / API routes)
6. tests
```

---

### Epic 1 — Cleanup (V1 Removal)

**Goal:** Remove everything that no longer serves the V2 vision. Creates a clean baseline.

**Scope:**
- Delete `LastFmAdvisorAdapter` and its tests, WireMock stubs, settings
- Delete `discover_similar` use case, its input, CLI command, and tests
- Delete `provider_sync_library` use case, its input, CLI commands, and tests
- Delete `provider_oauth_redirect` and `provider_oauth_callback` use cases *OR* slim them to write-only scopes (decide: keep OAuth for playlist output or make playlist output optional)
- Delete `Artist` entity, `ArtistRepository` port, `ArtistSQLRepository`, `ArtistModel`, and the DB migration that removes the table
- Remove `TOP`, `SAVED`, `PLAYLIST` values from `TrackSource` enum; update `Track` entity and `TrackModel`
- Remove `SpotifyLibraryPort` methods that only served sync (top_artists, saved_tracks, etc.); keep `search_tracks`, `create_playlist`, `update_playlist`
- Remove `AdvisorPort` implementations for Last.fm; keep Gemini

**Risk:** migrations are destructive — plan DB migration carefully, ensure backups noted.

---

### Epic 2 — Blacklist System

**Goal:** Let users permanently exclude artists, tracks, or genres from all future recommendations. The blacklist lives in the DB, not in the profile — it survives profile rebuilds.

**Scope:**

*Domain:*
- New entity: `BlacklistedArtist` (id, user_id, artist_name, created_at)
- New entity: `BlacklistedTrack` (id, user_id, fingerprint, name, artist_name, created_at)
- Optional: `BlacklistedGenre` (id, user_id, genre, created_at)

*Application:*
- New port: `BlacklistRepository` (add_artist, add_track, remove_artist, remove_track, get_all_for_user)
- New use cases: `blacklist_add_artist`, `blacklist_add_track`, `blacklist_remove`, `blacklist_list`

*Infrastructure:*
- New DB tables + migration
- `BlacklistSQLRepository`

*Entrypoints:*
- CLI: `muse blacklist add-artist <name>`, `muse blacklist add-track <name> --artist <artist>`, `muse blacklist remove <id>`, `muse blacklist list`

*Integration:*
- `discover_taste` fetches the user's blacklist and passes it to the Gemini advisor as explicit exclusions
- `GeminiAdvisorAdapter.get_discovery_strategy()` gains a `blacklisted_artists: list[str]` and `blacklisted_tracks: list[str]` parameter

---

### Epic 3 — Profile Enhancement

**Goal:** Enrich the taste profile with negative preferences, and make the profiler model configurable per build step.

**Scope:**

*Negative preferences in profile:*
- Add `negative_preferences: dict[str, float]` to `TasteProfileData` (AI-inferred dislikes — softer than the blacklist, lives inside the profile)
- Update Gemini profiler prompts to explicitly identify what the user seems to avoid (genres, eras, energy levels)
- The `discover_taste` use case reads both `negative_preferences` (from profile) and the blacklist (from DB) and passes both to the advisor

*Configurable model per step:*
- The three profiler methods (`build_profile_segment`, `merge_profiles`, `reflect_on_profile`) each accept an optional `model: str | None` parameter
- Gemini profiler adapter maps this to the actual model ID used in the API call
- New settings: `GEMINI_PROFILER_SEGMENT_MODEL`, `GEMINI_PROFILER_MERGE_MODEL`, `GEMINI_PROFILER_REFLECT_MODEL`
- CLI `muse taste build` gains `--segment-model`, `--merge-model`, `--reflect-model` flags (override settings)
- Update `TasteProfile.metadata` to record which model was used per step

*Profiler port rename:*
- Rename `build_profile_segment` → more clearly named; confirm consistent naming across port/adapter/use case

---

### Epic 4 — Discovery Quality

**Goal:** Improve the accept rate from ~5% by injecting richer context and reducing output volume.

**Scope:**
- Reduce default `playlist_size` from 20 to 8 (configurable)
- Pass `negative_preferences` (from profile) to the advisor alongside the profile
- Pass `blacklisted_artists` and `blacklisted_tracks` (from blacklist) to the advisor
- Improve `GeminiAdvisorAdapter` system prompt to:
  - Use `behavioral_traits` (openness, adventurousness) from the profile to calibrate risk
  - Explicitly list artists/genres to avoid
  - Prioritize specificity over volume ("give me 8 tracks you are highly confident about, not 20 guesses")
- Remove `discover_similar` and consolidate all discovery into `discover_taste`

---

### Epic 5 — Feedback Loop (CLI MVP)

**Goal:** Let users mark discovery results as liked/disliked. Disliked items auto-populate the blacklist.

**Scope:**

*CLI command:*
- `muse discover feedback <playlist-name>` — fetches the playlist's tracks from the discovery session (needs to be stored — see below), presents each one interactively: `[y]es / [n]o / [s]kip`
- Tracks marked `n` → automatically added to `blacklist_track` (and optionally their artist to `blacklist_artist` if the user chooses)

*Storage:*
- Discovery sessions need to be persisted. New entity: `DiscoverySession` (id, user_id, profile_id, created_at, strategy, tracks: list[SuggestedTrack])
- Or simpler: store the track list JSON directly on the session row (JSONB)
- CLI: `muse discover list` to see past sessions

*Note:* This epic is non-trivial because it requires the user to listen first and come back later. The CLI approach is the near-term MVP. A future UI would make this flow natural. Don't block other epics on this one.

---

### Epic 6 — Multi-Provider History Import

**Goal:** Accept listening history from providers beyond Spotify.

**Scope:**
- The `HistoryImportPort` / `StreamingHistoryParser` interface (if it doesn't already exist cleanly) should be a proper port
- New adapters: Apple Music export (CSV), Tidal export (CSV), potentially Last.fm scrobble export
- CLI: `muse import history --provider <spotify|apple|tidal> --file <path>`
- Keep Spotify export as the reference implementation

**Note:** Spotify's export format is already working. This epic is additive — implement each new provider as a separate adapter behind the same port.

---

### Epic 7 — Code Hygiene

**Goal:** Address known tech debt from V1 and ROADMAP.txt.

**Scope (can be broken into micro-tasks):**
- Rename `adapter/client.py` → `<adapter>/adapter.py` across all infrastructure adapters
- Revisit `TasteProfile` uniqueness: `name` vs `(user_id, profiler_type)` — pick one and enforce it
- Add GIN index on `genres` fields in DB (artist + track tables) — use `EXPLAIN ANALYZE` first
- Audit and remove dead code (post-cleanup)
- Reduce CLAUDE.md size — keep the minimum that's always needed, move verbose sections to CONVENTIONS.md
- Consider replacing Makefile with Just
- Add `direnv` support for local environment management

---

## Dependency Order

```
Epic 1 (Cleanup)
    → Epic 2 (Blacklist)
        → Epic 4 (Discovery Quality)  ← depends on blacklist being available
    → Epic 3 (Profile Enhancement)
        → Epic 4 (Discovery Quality)  ← depends on negative_preferences in profile
    → Epic 5 (Feedback Loop)          ← depends on cleanup (no discover_similar)

Epic 6 (Multi-Provider Import)        ← independent, can run anytime
Epic 7 (Code Hygiene)                 ← independent, can run anytime or interleaved
```

Epic 1 is the prerequisite. Epics 2 and 3 can run in parallel. Epic 4 needs both 2 and 3 to be meaningful. Epic 5 is a standalone after Epic 1.

---

## How to Use This Document

When starting an epic, create a focused implementation plan (in `/plans/`) that:
1. Scopes the specific changes within that epic
2. Lists the files to create/modify, layer by layer (domain → ports → adapters → use cases → entrypoints)
3. Describes the test strategy

This top-level document stays stable as the north star. Sub-plans get created, executed, and archived.
