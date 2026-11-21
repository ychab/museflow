# MuseFlow agent guidelines

The single instruction file for coding agents. Claude Code reads it natively: never add a `CLAUDE.md` or
`CLAUDE.local.md`, which would replace it. Testing rules live in `tests/AGENTS.md`, loaded when working under `tests/`;
schema change rules in `migrations/AGENTS.md`.
Claude Code skills (`/arch-review`, `/security-review`) and the `test` agent live in `.claude/`.

## Stack & tools
- **Python:** 3.14 managed by `uv`
- **Frameworks:** FastAPI (API), Typer (CLI), SQLAlchemy 2.0 async, Pydantic v2
- **HTTP:** httpx (async), tenacity (retry logic)
- **Quality:** Ruff, mypy (strict), deptry; pytest + polyfactory + WireMock, 100% branch coverage
- **DB:** PostgreSQL only (PostgreSQL-specific features throughout)

## Commands
- `make install` — install deps + pre-commit hooks
- `make lint` — format + type check + dependency check + import contracts (`lint-imports`)
- `make test` — all tests with 100% branch coverage (`make test-unit` / `make test-integration` for targeted runs)
- `make up` / `make down` — Docker (DB + WireMock)
- `make run` — FastAPI dev server; `make docs-build` — strict docs build

Before considering a task done, run `make lint` and the relevant tests.

## Language
Everything written for the repo is in English, whatever the conversation language: code, comments, docstrings, logs,
CLI help, tests, commit messages, issues, PR descriptions, plans and docs.

## Architecture: Clean / Hexagonal

```
museflow/
├── domain/          # Pure Python — NO framework imports ever
│   ├── entities/    # frozen dataclasses
│   ├── value_objects/ # business values: words of the domain language (a listening period, a blacklist)
│   ├── mappers/     # pure functions between two domain shapes (entity ↔ value object)
│   ├── utils/       # pure functions (text normalization, fingerprinting, locale validation)
│   ├── exceptions.py
│   ├── enums.py     # all StrEnum / IntFlag definitions
│   ├── const.py     # all domain constants
│   └── types.py     # type aliases only
├── application/     # Orchestration — depends ONLY on domain
│   ├── use_cases/
│   ├── services/    # application services, shared by use cases (e.g., record_llm_usage)
│   ├── utils/       # pure helpers shared by use cases
│   ├── inputs/      # command/input schemas
│   ├── outputs/     # shapes handed to the entrypoints for display, by theme (stats, LLM usage, progress events)
│   ├── mappers/     # pure functions from a domain shape to an input schema
│   └── ports/       # ABC interfaces (unit of work, repositories, providers, advisors, security, file storage)
└── infrastructure/  # Implements ports
    ├── adapters/    # database (models, repositories, unit of work), providers, advisors, enrichers, profilers, progress,
    │                # storage
    ├── config/settings/
    ├── entrypoints/ # api (FastAPI), cli (Typer), wiring.py (the adapters, built for all of them)
    └── utils/       # pure helpers shared by adapters and entrypoints (formatting)
```

The layering is enforced by import-linter: the contracts live in `pyproject.toml` (`[tool.importlinter]`).

## Domain
- Entities are `@dataclass(frozen=True, kw_only=True)` with no framework imports. Canonical: `domain/entities/track.py`.
- Business rules only, in `__post_init__`. Never enforce DB limits (varchar lengths) here.
- Permanent computed fields (fingerprint, normalized genres): set in `__post_init__` with `object.__setattr__`.
  Dynamic fields: `@property`.
- External IDs and slugs are passed in by the mapper, never generated in the entity.

## Application
- **Ports** are `abc.ABC` + `@abstractmethod`. They accept input schemas and return domain entities or outputs.
- **Outputs** (`outputs/`) are the frozen dataclasses the use cases and ports hand over for display, with no business
  rule: statistics, an LLM usage summary, progress events. The test is what a shape is, not which layer uses it: a
  word of the domain language (a listening period, a discovery strategy) is a value object of the domain, even when
  only the application handles it. A `*Result` / `*Report` stays in its use case module; `outputs/` holds what
  several use cases or a port share, in the module of its theme (`outputs/stats.py`).
- **Inputs** are Pydantic `BaseModel` or `@dataclass(frozen=True, kw_only=True)`, named as in [Naming](#naming).
- **Use cases** are standalone async functions by default (`use_cases/user_create.py`). Use a class with a named method
  when it holds injected dependencies and is called with user-specific args (`use_cases/track_history_import.py`), and a
  class with one method per step when the entrypoint calls several steps of one flow, e.g. find, confirm, then delete
  (`use_cases/track_delete.py`): what scopes the whole flow (user, provider) goes in `__init__`, so every step
  shares it.
- **Every entrypoint action goes through a use case**, even a thin one that only reads a repository
  (`use_cases/taste_profile_list.py`): the use cases list what the application does, and an API reuses them as is.
  The entrypoint keeps only its own concerns (parsing, finding the user, output).
- **Application services** (`services/`) hold orchestration shared by several use cases, ports included
  (`services/discovery.py`). A service is a class: the ports it uses go in `__init__`, the per-call inputs in its
  methods. A use case builds it in its own `__init__` from the ports injected there; it is never injected itself, as it
  is application code, not a boundary: tests mock its ports, not the service. Only use cases call them, never an
  entrypoint; a use case never calls another use case. Pure helpers without ports go in `utils/`, and a step of a
  service that needs no port moves there too (`utils/discovery.keep_new_tracks`).
- Ports come in as parameters (DI). Never instantiate a repository in a use case: reach it through the unit of work
  (`uow.tracks`, `uow.playlists`, …).
- **The use case owns the transactions.** Each `async with uow:` block is one short transaction: a clean exit commits,
  an exception rolls back, `await uow.rollback()` discards on purpose. Open a block per step:
  - reads that feed a remote call (LLM, provider) sit in a block closed **before** the call: never a remote call, a
    user prompt or a long wait inside a block (`DATABASE_IDLE_IN_TRANSACTION_TIMEOUT` kills such a session);
  - a step that must survive a later failure (paid LLM batch, checkpoint, import chunk) gets its own block;
  - writes that must succeed or fail together (a partial state would be *wrong*, not merely incomplete) share one block.
  When a flow mixes a remote side effect with local writes, do the remote call first. Blocks don't nest; one `uow`
  instance serves one flow at a time.

## Infrastructure
- **Shared code:** `adapters/common/` holds adapter code shared by several adapters of one kind (the OpenRouter client,
  validation and self-healing of the LLM adapters in `common/llm/`). A pure helper that adapts nothing (formatting a
  duration) goes in `infrastructure/utils/`, grouped by subject in a few modules, never one module per function: the
  entrypoints import it there without reaching into an adapter.
- **Wiring:** the `Wiring` class (`entrypoints/wiring.py`) builds each adapter from the settings and the resources of
  the process (the session factory), in one place for every entrypoint. It is the composition root of the process:
  it holds the process resources and builds the adapters (what other stacks call a DI container). Each entrypoint opens one per process with
  `Wiring.open()`, which creates those resources in the running event loop and closes them on exit, then reaches it
  through its own `get_wiring` (a FastAPI dependency, `cli/dependencies.py`). Its methods are `build_*`
  (`wiring.build_provider_library(...)`): a new instance the caller owns, an async context manager when the adapter
  holds a client, apart from a CRUD `create` and from the `get_*` that hand over what the entrypoint already holds.
  A resource of the process (a pool, a client) goes in `open()` and the constructor, never in a `build_*` signature.
  The wiring imports no entrypoint nor framework (import-linter).
- **Models** (canonical: `database/models/track.py`):
  - A schema change never adds a migration while in development: follow `migrations/AGENTS.md`.
  - `MappedAsDataclass` + `Base`; `id`, `created_at`, `updated_at` come from mixins (`init=False`).
  - The class is `<Entity>Model` (`TrackModel`), imported under that name, never an alias.
  - `from_entity(cls, entity)` and `to_entity(self)`, each only when the application calls it: no dead code to keep
    the pair. Repositories build rows with `from_entity` when the port takes an entity, never field by field; a port
    that takes an input schema (`users.create`) builds the row from it, with no `from_entity`.
  - `JSONB` and `ARRAY(String)` from `sqlalchemy.dialects.postgresql`; `@declared_attr` for dynamic `__table_args__`.
- **Repositories** (canonical: `database/repositories/users.py`):
  - Take an `AsyncSession`; SQLAlchemy 2.0 `select/update/delete`; `.scalar_one_or_none()` / `.scalar_one()`.
  - **Never commit**: the unit of work commits. The session has `autoflush=False`: `flush()` after ORM changes
    (`session.add`, attribute changes) so constraints fail inside the method, then `refresh()` if needed. Statements
    run with `session.execute(insert/update/delete)` hit the database at once and need no flush.
  - `.returning()` instead of an extra SELECT; key returned rows by a column (e.g. fingerprint), never by position.
  - Upserts with `pg_insert(...).on_conflict_do_update(...)`.
  - A new repository is added to `UnitOfWorkPort` and `SQLUnitOfWork.__aenter__`.
- **External APIs** (Spotify, OpenRouter): DTOs are Pydantic models matching the external shape exactly; standalone mapper
  functions (`to_domain_track(dto) -> Track`) hold the transformations (`providers/spotify/mappers.py`).
- **API schemas** (`entrypoints/api/schemas/`): one module per endpoint module, named alike (`schemas/playlists.py`
  for `v1/endpoints/playlists.py`); `schemas/common.py` holds what every theme reuses (`ProblemDetails`,
  `PageResponse[T]`, `SuccessResponse`).
- **API errors** (`entrypoints/api/errors.py`): a route catches no domain exception. Each one it lets through gets a
  `Problem` (status, fixed detail) in `PROBLEMS`, answered as an RFC 9457 problem details body; another user's object
  is a 404, as an unknown one. A collection is paged with `get_page_params` and `PageResponse[T]`.
- **CLI:**
  - Each Typer command is a thin sync wrapper calling `run_logic()` (`cli/dependencies.py`) on a co-located
    `<command>_logic` function (never a `_`-prefixed name): it runs the logic like `asyncio.run()`, with the wiring
    opened for the run and closed at the end. A command that must print between two steps runs them in one
    `init_logic_runner()` (`provider/connect.py`): the pooled connections are bound to its event loop. The logic
    builds what it needs from `get_wiring()`, held in a local `wiring` when it builds several things.
  - The callback is `<group>_<command>_command`, its logic `<group>_<command>_logic`, one
    `<group>_<command>_<step>_logic` per step when the command runs several (`provider_connect_start_logic`), with the
    CLI names (dashes become underscores). The group looks redundant inside its module, but a reader skimming a test
    or a search result sees which command it is (`playlist_history_logic`, not `history_logic`), and every name stays
    unique. The decorator always names the command (`@app.command("history")`): without it, Typer would derive
    `playlist-history-command` from the function name.
  - `*_logic` returns data or raises; it never prints. All output (messages, Rich tables) belongs in the
    `@app.command` callback. Exception: an interactive prompt that drives the logic mid-loop, with what it shows the
    user to answer (the track before its rating, the tracks listed before a delete confirmation).
  - Option order: filters (`--force`, `--provider`), then processing config (`--batch-size`), then the cap (`--limit`).
  - Output reads in blocks: a step with its details, a panel, a table, the cost line. One blank line sets a block
    apart from the next, never inside one, never two in a row.
  - `--verbose` shows the user the details of a run, rendered from the progress events and the results; DEBUG logs
    are the developer's diagnostics, set by the environment. Never a DEBUG line to tell the user something, nor a
    `--verbose` detail that only repeats a log.

## Naming
| Name | Meaning | Type |
|------|---------|------|
| `user` | Domain entity | frozen dataclass |
| `user_db` | SQLAlchemy model | MappedAsDataclass |
| `user_in` | Input schema | Pydantic / dataclass |
| `user_dto` | External API DTO | Pydantic |

Functions and use case classes start with a verb, classes holding data are nouns; the object is the noun of the data
(`enrichment`, `ratings`), the verb names the action only (`enrich`, `rate`). Use cases speak CRUD (`create`, `get`,
`update`, `delete`) whenever it fits, a domain verb otherwise (`import`, `enrich`, `rate`): they display
nothing and other use cases reuse them. Entrypoints use the concrete user-facing verb (`taste view` calls
`get_taste_profile`). Modules put the theme first so that `ls` groups a feature, which also keeps the module name
apart from its function (`user_create.create_user`). The theme is one of a closed list of features, singular:
`user`, `provider`, `track`, `taste`, `playlist`, `blacklist`, `stats`, `llm_usage`; a new feature adds its theme
here. A use case covers one object (`track_history_import`, not `history_import`): another object gets its own use
case, so its own module.

| What | Pattern | Example |
|------|---------|---------|
| Use case module | `<theme>[_<object>]_<verb>.py`: the object when it is not the theme, the verb of the function; `list` for a collection read | `track_ratings_import.py`, `playlist_get.py`, `playlist_list.py` |
| Use case function / class | `<verb>_<object>` / `<Verb><Object>UseCase` | `import_ratings`, `EnrichTracksUseCase` |
| Read use case | `get_`, the plural says a collection; `count_` a number | `get_taste_profile`, `get_taste_profiles` |
| Use case outcome | `<Verb><Object>Report` for a batch run, `<Verb><Object>Result` otherwise; a read names the object alone, its verb only says how the data is fetched | `ImportRatingsResult`, `TopTagsResult` |
| Entity write input | `<Entity><Action>Input` | `UserCreateInput` |
| Flow config input | `<Verb><Object>ConfigInput` | `EnrichTracksConfigInput` |
| Imported file entry | `<Noun>EntryInput` | `RatingEntryInput` |
| Repository method | The repository names the object: `get` / `get_by_<field>` one, `get_list` a filterable collection, `get_<other>s` another object; `create`, `update`, `delete`, `bulk_<verb>` for a batch, `purge` all of a user's rows; a domain verb when it fits better | `tracks.get_list`, `get_track_ids`, `bulk_upsert`, `consume` |

Never name a method after a builtin type (`list`, `dict`, `set`, `type`): in its class body it hides the builtin, and
every annotation of the class that uses it (`list[Track]`) then names the method.

## Types & style
- Strict type hints everywhere, tests included. `str | None`; IDs are `uuid.UUID`, except the technical
  records of the OAuth flow (state, provider token), which keep an `int`. No `Any` unless justified.
- A signature fits on one line, or has one parameter per line with a trailing comma; never all parameters together on
  one indented line.
- Parameters grouped by role: inputs first, then the unit of work, then other ports. DI parameters stay contiguous;
  a new port goes next to the others, never at the end.
- No single-letter names, except in comprehensions, lambdas, loop indexes and `except ... as e`.
- Public members first, private helpers (`_`-prefixed) after: a reader opens a module for what it exposes. A helper
  run at import time (a decorator argument such as `_is_retryable_error`, a module-level constant) stays above its
  first use. Group members by kind; never class/function/class.
- No `return` inside a `try` block that has a `finally:`: assign the result in the `try`, then return it after the
  statement, so the exit point stays visible.
- No duplicated inner functions: a closure repeated in several places becomes a decorator or shared helper
  (e.g. `@self_heal`).
- A helper that only builds instances of one class is a classmethod of it, an alternative constructor named after
  what it builds from (`SpotifySearchArtistQuery.by_release_years`), not a module function next to it; what only
  shapes the build (the current year) is a parameter, not a field. A mapper between two shapes (DTO or input to
  entity) stays a standalone function, as does a builder from an input the class's layer must not know.
- A standalone mapper is named `to_<target>`: its module names the source (`spotify/mappers.py`:
  `to_domain_track`). When two sources of one module give the same target, it adds `_from_<source>`
  (`to_domain_track_from_episode`). A bare `from_<source>` is a classmethod, whose class names the target
  (`TrackModel.from_entity`).
- Every constant is `Final[T]`: in a class body too, where `Final` alone already makes it a class variable. A constant
  only one class uses lives in that class (`_`-prefixed when private); module level is for one several members of the
  module share, one imported elsewhere, or one only a Pydantic model uses (in a model body, `Final` turns into a field
  or a private attribute).
- **Blank lines** split a body into its steps, never inside one. A statement that exists only for its neighbour
  belongs to its step:
  - a block (`for`, `while`, `with`, `try`, an `if` chain, `match`) or a statement spanning several lines is a step,
    with one blank line before and after; a variable only that block uses sticks to it;
  - a guard (`if` without `else` ending with `raise`, `return`, `continue`, `break`) sticks to the statement it checks
    or to the one it makes possible; checks of one kind in a row (validation, confirmation) form one step;
  - a default that the next `if` overrides sticks to it; a result that the body accumulates (a list, a counter) is a
    step of its own when the body starts with it, set apart from the `return`; set further down, it sticks to the
    loop that fills it, as does what finishes it (a sort);
  - a database access always breathes, so that no remote call slips into a transaction: an `async with uow:` block, or
    a repository call among other statements, has one blank line before and after, which wins over the rules above;
    several calls in a row form one step;
  - the closing log, or an `if ...: return` right above, sticks to the final `return`;
  - a body of one or two statements stays compact; a table printed by a command (its columns, the loop adding its
    rows, the print) is one step; in tests, arrange / act / assert.
- No docstrings for obvious code; only for ports, complex algorithms and non-obvious `Raises:`. Google style, without
  repeating the types.

## Logging and errors
- `logger = logging.getLogger(__name__)`. Levels: ERROR unrecoverable, WARNING handled but unexpected, INFO milestones
  only, DEBUG flow.
- f-strings are fine for messages. Add `extra={}` when the data is worth querying in an aggregator (IDs, counts):
  only the `json` handler ships it. The message stands alone all the same: the terminal handlers (`console`, `rich`)
  never print `extra`, so a warning needs its context (status code, step, track) in the text. Streams, handlers and
  `--verbose` vs DEBUG: `docs/technical/logging.md`.
  In `except` blocks, the traceback carries an unexpected error: `logger.exception(...)`, or
  `logger.warning(..., exc_info=True)` when the run goes on; the message gives the context. An expected error that
  its message explains (a rate limit, a rejected query) logs no traceback.
- Never log secrets (tokens, passwords): log IDs.
- Domain exceptions live in `domain/exceptions.py`; adapter-specific ones in their adapter package.
- An exception ends in `Error`, as in the standard library (`ValueError`): `UserNotFoundError`, even when the caller
  handles it as an expected outcome (`TasteProfileBuildPausedError`). Only a control-flow signal that never reaches a
  user drops the suffix, like `StopIteration` (`RateLimitRetry`, caught by the retry loop).
- In tenacity adapters, `_is_retryable_error()` explicitly returns `False` for every non-retryable exception.
- No `assert` in production code (Ruff S101): raise `ValueError` at the top of the function for contract violations;
  where mypy can't narrow after the guard, use `# type: ignore[union-attr]` at the call site.

## Issues and PRs
- The backlog lives in GitHub issues; a PR closes its issue with `Closes #N`.
- An issue is short: a context paragraph, **Plan**, then **Done when** (or **Next time it fails** for a bug not yet
  reproduced, e.g. #85). Labels come from the repo's list.
- Issues, PRs and docs are public: never real user data (genres, artists, taste profiles, listening history), only
  counts, costs and fictional examples.

## Testing
100% branch coverage; integration tests first, unit tests for error paths. Full rules: `tests/AGENTS.md`.

**Dead End Protocol:** after 3 failed attempts to fix the same problem, stop and report options A/B/C instead of
looping.
