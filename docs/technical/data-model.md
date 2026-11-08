# Data model

PostgreSQL only, by design: the schema uses `JSONB`, `ARRAY`, `ON CONFLICT DO UPDATE` and `xmax`-based insert detection, and none of that is hidden behind a portable abstraction. Tables are prefixed `museflow_`. Every user-owned table has a `user_id` foreign key with `ON DELETE CASCADE`, so deleting a user removes all of their data.

```mermaid
erDiagram
    USER ||--o{ TRACK : owns
    USER ||--o{ PLAYLIST : owns
    USER ||--o{ TASTE_PROFILE : owns
    USER ||--o{ BLACKLISTED_ARTIST : owns
    USER ||--o{ BLACKLISTED_TRACK : owns
    USER ||--o{ AUTH_TOKEN : owns
    USER ||--o{ AUTH_STATE : owns
    USER ||--o{ LLM_USAGE : spent
    PLAYLIST ||--o{ PLAYLIST_TRACK : contains
    TRACK ||--o{ PLAYLIST_TRACK : appears_in
    TRACK ||--o{ TRACK_PLAY : played
    TASTE_PROFILE |o--o{ PLAYLIST : guided
    TASTE_PROFILE |o--o{ LLM_USAGE : cost
    PLAYLIST |o--o{ LLM_USAGE : cost

    USER {
        uuid id PK
        string email UK
        string hashed_password
        bool is_active
    }
    TRACK {
        uuid id PK
        uuid user_id FK
        string name
        jsonb artists
        string album_name
        string fingerprint
        jsonb provider_links
        int source
        int score
        bool score_skipped
        array genres
        array moods
        array locales
    }
    TRACK_PLAY {
        int id PK
        uuid track_id FK
        timestamp played_at
    }
    PLAYLIST {
        uuid id PK
        uuid user_id FK
        string provider
        string provider_id
        string type
        string name
        uuid profile_id FK
        text reasoning
        string focus
    }
    PLAYLIST_TRACK {
        uuid id PK
        uuid playlist_id FK
        uuid track_id FK
        int position
    }
    TASTE_PROFILE {
        uuid id PK
        uuid user_id FK
        string name
        jsonb profile
        string status
        jsonb checkpoint_profile
        int checkpoint_batch_index
    }
    BLACKLISTED_ARTIST {
        uuid id PK
        string artist_name
        string fingerprint
    }
    BLACKLISTED_TRACK {
        uuid id PK
        string name
        string artist_name
        string fingerprint
    }
    AUTH_TOKEN {
        int id PK
        string provider
        string token_access
        string token_refresh
        timestamp token_expires_at
    }
    AUTH_STATE {
        int id PK
        string provider
        string state UK
    }
    LLM_USAGE {
        uuid id PK
        uuid user_id FK
        uuid run_id
        string operation
        uuid profile_id FK
        uuid playlist_id FK
        string step
        string model
        int calls
        int prompt_tokens
        int completion_tokens
        int reasoning_tokens
        numeric cost
        interval duration
    }
```

The diagram omits audit columns (`created_at`, `updated_at`, provided by a mixin) and a few Playlist columns (`snapshot_id`, `genre`, `mood`, `custom_instructions`). Models live in [`museflow/infrastructure/adapters/database/models/`](https://github.com/ychab/museflow/tree/main/museflow/infrastructure/adapters/database/models); the matching frozen-dataclass entities live in [`museflow/domain/entities/`](https://github.com/ychab/museflow/tree/main/museflow/domain/entities).

## Track and its plays

A streaming-history export is an event log: one line per play. MuseFlow keeps both levels: **one row per track**
(`museflow_track`: name, artists, rating, enrichment) and **one row per play** (`museflow_track_play`: the track and
when it was played, unique on `(track_id, played_at)`).

| Level | Rows for the author's history | What it serves |
|---|---|---|
| Track | ~11,300 after filtering | Everything about a song: identity, rating, enrichment, playlists |
| Play | ~228,000 after filtering | When each track was listened to: play counts, first and last play, listening per period |

The ~228k and ~11k figures come from the author's own export (see [What my data taught me](../product/insights.md)). Two
import filters shrink the data: plays shorter than the minimum duration (`--min-duration-played`, default 90 seconds)
are skipped, and so are entries with no timestamp or no Spotify track id (counted in the import report).

**The plays are the only source of play data.** A track has no play column: every query that loads tracks joins
`plays_summary()` ([source](https://github.com/ychab/museflow/blob/main/museflow/infrastructure/adapters/database/repositories/track_play.py)),
a `JOIN LATERAL` subquery that counts each track's plays and takes the first and last, in one pass over the
`(track_id, played_at)` index; its columns also serve the date filters and the ordering. The model's `to_entity`
requires the three values, so a query that forgets the join does not type-check. The `Track` entity carries them as
read-only fields: computed when loaded, never written. An earlier design stored them as columns, merged at each import: two sources of truth, and a timeline reduced
to the last play, which dated a track replayed years later by its last listen only (#139). A track with no play,
such as a discovery never listened to, has a count of 0 and no dates.

Re-import is idempotent. The plays are inserted with `ON CONFLICT DO NOTHING`, so the same files add none.
`TrackRepository.bulk_upsert` ([source](https://github.com/ychab/museflow/blob/main/museflow/infrastructure/adapters/database/repositories/track.py))
uses `INSERT ... ON CONFLICT (user_id, fingerprint) DO UPDATE` with per-column merge rules:

| Column | On conflict |
|---|---|
| `source` | bitwise OR, so a track found in history and later suggested keeps both flags |
| `score` | keep existing unless null (`COALESCE`), a re-import never overwrites a rating |
| `provider_links` | JSONB concatenation |
| `score_skipped`, `genres`, `moods`, `locales` | **never updated**, so user decisions and enrichment survive a re-import |

The last row is a deliberate asymmetry: derived data from the import may be refreshed, human or LLM-added data may not. The restore path for ratings and enrichment is the `rate` and `enrich` export / import commands, not the importer.

### Identity: the fingerprint

A track is identified by a **fingerprint**, not by a provider id: `normalize(name)|normalize(primary_artist)` ([`museflow/domain/utils/text.py`](https://github.com/ychab/museflow/blob/main/museflow/domain/utils/text.py)). Normalisation transliterates to ASCII, lowercases, strips bracketed `feat` / `remaster` / `live` / `edit` / `version` suffixes and punctuation. For example `My Song (Remastered 2011)` by `Some Artist` becomes `my song|some artist`.

Why not the provider id:

- **Cross-provider identity.** The same recording has different ids on different providers. `provider_links` is a JSONB list of `{provider, provider_id}` pairs, so one row can carry several.
- **Re-releases.** The same song appears under several Spotify ids (single, album, remaster). History import collapses them (their play times are merged) and the discovery filter excludes anything whose fingerprint is already known.
- **Blacklist and ratings follow the song**, not one catalogue entry.

The cost is false merges (two different songs with the same normalised title and primary artist) and false splits (spelling variants). The fingerprint is computed in the entity's `__post_init__` and indexed; the unique constraint is `uq_museflow_track_user_fingerprint` on `(user_id, fingerprint)`.

!!! note "Uniqueness evolved"
    Commit `8b27c95` first made the constraint `(user_id, provider, fingerprint)`; `edb1fd9` ("splitting providers") replaced it with `(user_id, fingerprint)` plus the `provider_links` list. The provider is therefore not part of uniqueness today.

### Source, score and skip flags

| Field | Meaning |
|---|---|
| `source` | `TrackSource` is an `IntFlag` stored as an integer: `HISTORY = 1`, `DISCOVERY = 2`. A bit field rather than an enum so one track can be both (imported from history, or suggested then later heard) without a join table |
| `score` | Optional rating, `0` to `10` (`DISCOVERY_TRACK_SCORE_MIN/MAX`). `0` means actively disliked; an interactive rating that is at or below `DISCOVERY_BLACKLIST_SCORE_THRESHOLD` (3) prompts the user to blacklist the track and its artist, tracks at or above `DISCOVERY_LIKED_SCORE_THRESHOLD` (7) feed the advisor as taste anchors, capped by `DISCOVERY_LIKED_TRACKS_LIMIT` (200) |
| `score_skipped` | The user chose not to rate this track and not to be asked again |
| `genres`, `moods`, `locales` | Enrichment output (below). Postgres `ARRAY(String)` for the lists; `locales` holds ISO 639-1 codes of every sung language. `locales` is nullable and the distinction matters: `NULL` means never enriched (or the call failed) so the track is eligible for enrichment, `[]` means the model answered that there is no sung language (instrumental, or no reliable signal) so the track is not re-sent unless `--force` |

Discovery tracks are written to the same table (without plays) so they are excluded from later sessions by the same fingerprint check as played tracks.

### Genre and mood vocabularies

Free-text tags from an LLM are not queryable or comparable, so enrichment and profiling are constrained to closed vocabularies defined in [`museflow/domain/enums.py`](https://github.com/ychab/museflow/blob/main/museflow/domain/enums.py) and grouped in [`museflow/domain/const.py`](https://github.com/ychab/museflow/blob/main/museflow/domain/const.py).

| Vocabulary | Size | Shape |
|---|---|---|
| `GenreTag` macro | 13 | Broad umbrella, for example `hip-hop`, `electronic`, `rock`, `jazz`, `world` |
| `GenreTag` meso | 60 | Sub-genre of a macro, for example `house`, `post-rock`, `neo-soul` |
| `GenreTag` micro | 93 | Finest level, optional |
| `MoodTag` | 12 | `energetic`, `chill`, `melancholic`, `upbeat`, `aggressive`, `romantic`, `focus`, `party`, `introspective`, `euphoric`, `peaceful`, `dark` |

A track's `genres` list is ordered `[macro, meso, micro?]`, so the first element is always the broadest class and the list is usable at any granularity without a separate column per level. The taxonomy is one flat enum with the level encoded by tuple membership (`GENRE_MACRO_TAGS`, `GENRE_MESO_TAGS`, `GENRE_MICRO_TAGS`), which keeps the stored value a plain string and lets a taxonomy change be handled by re-enriching (`enrich tracks --force`) rather than by a migration.

## Playlist: one entity, a type discriminator

`museflow_playlist` stores both kinds of playlists in one table with a `type` column (`PlaylistType`): `DISCOVERY` (AI-curated) and `HISTORY` (a persisted "best of" from the user's own library). They were once two separate concepts (an ephemeral playlist and a persisted discovery playlist) and were merged (commit `467a4ce`) so a new type does not need a new table. Columns specific to discovery (`profile_id`, `reasoning`, `focus`, `genre`, `mood`, `custom_instructions`) are nullable and set only for that type, recording *why* the playlist exists. Membership and order live in `museflow_playlist_track` (`position`).

`profile_id` references the taste profile with `ON DELETE SET NULL`: deleting a taste profile keeps the discovery playlists it guided (they can still be listed and rated) and only drops the link. The column is informational; no code reads it back.

## Taste profile

`museflow_taste_profile` holds one named profile per user (`UNIQUE (user_id, name)`). The profile itself is a `JSONB` document typed by the `TasteProfileData` TypedDict in the domain:

| Section | Content | Produced by |
|---|---|---|
| `taste_timeline` | List of eras: label, time range, a five-value technical fingerprint (energy, acousticness, rhythmic complexity, atmosphere, instrumentalness), dominant moods | segment + merge |
| `core_identity` | Long-term affinities, tag to weight in `[0, 1]` | segment + merge |
| `current_vibe` | What the latest batch reveals right now | segment + merge (replaced each time) |
| `personality_archetype`, `life_phase_insights`, `musical_identity_summary`, `behavioral_traits`, `discovery_style` | Narrative and numeric traits | final reflection |

Document storage fits because the profile is read and written as a whole, never queried by section, and its shape is owned by a prompt that will keep evolving. `logic_version` and `profiler_metadata` (the gateway and the model settings of each step) are stored beside it so a profile can be traced to the code and models that produced it.

**Checkpointing** reuses the same row. While a build runs, each completed batch upserts the partial profile into `profile`, sets `status = BUILDING`, and records `checkpoint_profile` and `checkpoint_batch_index`. `--resume` reads the checkpoint and continues from the next batch. On completion the row becomes `FINISHED` and the checkpoint columns are cleared. `discover` refuses a profile that is still `BUILDING`.

## LLM usage

`museflow_llm_usage` keeps what the LLM calls cost: one row per command run, step and model, with the calls, tokens,
cost (`NUMERIC(12, 6)`, in USD) and the time spent waiting for the replies (`INTERVAL`). `run_id` groups the rows of one run and `operation` (`LLMOperation`) names the command:
`taste_build`, `discover` or `enrich`. Rows are written at the end of the command, whatever its outcome (see
[Cost tracking](llm-pipeline.md#cost-tracking)).

It is a table of its own rather than a `cost` column on the profile and the playlist, because some spending has no
entity to carry it: an enrichment, a dry-run discovery, a failed one, a build paused before its first checkpoint.
`profile_id` and `playlist_id` are nullable and use `ON DELETE SET NULL`, so deleting a profile or a playlist keeps
its cost history. An index on `(user_id, created_at)` serves the per-user overview.

## Blacklist and authentication

- **Blacklist.** Two tables, `museflow_blacklisted_artist` and `museflow_blacklisted_track`, each unique on `(user_id, fingerprint)`. An artist fingerprint is just the normalised name; a track fingerprint is the same `name|artist` form as `museflow_track`. They are enforced twice at discovery time: sent to the advisor as "never suggest", and re-applied after reconciliation in case the advisor ignored the instruction.
- **Users.** `email` (unique) and an Argon2 password hash. The API issues JWT access tokens (HS256, 30 minutes by default); the CLI identifies a user by `--email` or `MUSEFLOW_CLI_DEFAULT_EMAIL` and does not authenticate.
- **Provider tokens.** `museflow_auth_token` stores the Spotify access and refresh token per `(user, provider)`, and `museflow_auth_state` stores the single-use OAuth `state`. Tokens are stored as plain strings in the database (see [Privacy & data](privacy-and-data.md)).

## Migrations

The project keeps a single squashed Alembic migration (`migrations/versions/initial.py`), edited in place during V2 development, consistent with a reset-and-re-import workflow rather than data-backfill migrations (commit `2fdd158` squashed the earlier ones). That is fine for a single-user project and would need to change before any multi-user deployment.
