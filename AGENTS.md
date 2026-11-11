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
│   ├── value_objects/
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
│   └── ports/       # ABC interfaces (unit of work, repositories, providers, advisors, security)
└── infrastructure/  # Implements ports
    ├── adapters/    # database (models, repositories, unit of work), providers, advisors, enrichers, profilers
    ├── config/settings/
    └── entrypoints/ # api (FastAPI), cli (Typer)
```

The layering is enforced by import-linter: the contracts live in `pyproject.toml` (`[tool.importlinter]`).

## Domain
- Entities are `@dataclass(frozen=True, kw_only=True)` with no framework imports. Canonical: `domain/entities/track.py`.
- Business rules only, in `__post_init__`. Never enforce DB limits (varchar lengths) here.
- Permanent computed fields (fingerprint, normalized genres): set in `__post_init__` with `object.__setattr__`.
  Dynamic fields: `@property`.
- External IDs and slugs are passed in by the mapper, never generated in the entity.

## Application
- **Ports** are `abc.ABC` + `@abstractmethod`. They accept input schemas and return domain entities.
- **Inputs** are Pydantic `BaseModel` or `@dataclass(frozen=True, kw_only=True)`, named as in [Naming](#naming).
- **Use cases** are standalone async functions by default (`use_cases/user_create.py`). Use a class with a named method
  when it holds injected dependencies and is called with user-specific args (`use_cases/history_import.py`), and a
  class with one method per step when the entrypoint calls several steps of one flow, e.g. find, confirm, then delete
  (`use_cases/tracks_delete.py`): what scopes the whole flow (user, provider) goes in `__init__`, so every step
  shares it.
- **Every entrypoint action goes through a use case**, even a thin one that only reads a repository
  (`use_cases/taste_profile_list.py`): the use cases list what the application does, and an API reuses them as is.
  The entrypoint keeps only its own concerns (parsing, finding the user, output).
- **Application services** (`services/`) hold orchestration shared by several use cases, ports included
  (`services/llm_usage.py`). Only use cases call them, never an entrypoint; a use case never calls another use case.
  Pure helpers without ports go in `utils/`.
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
- **Models** (canonical: `database/models/track.py`):
  - A schema change never adds a migration while in development: follow `migrations/AGENTS.md`.
  - `MappedAsDataclass` + `Base`; `id`, `created_at`, `updated_at` come from mixins (`init=False`).
  - Always both `from_entity(cls, entity)` and `to_entity(self)`, symmetric. Repositories build rows with
    `from_entity`, never field by field.
  - `JSONB` and `ARRAY(String)` from `sqlalchemy.dialects.postgresql`; `@declared_attr` for dynamic `__table_args__`.
- **Repositories** (canonical: `database/repositories/users.py`):
  - Take an `AsyncSession`; SQLAlchemy 2.0 `select/update/delete`; `.scalar_one_or_none()` / `.scalar_one()`.
  - **Never commit**: the unit of work commits. The session has `autoflush=False`: `flush()` after ORM changes
    (`session.add`, attribute changes) so constraints fail inside the method, then `refresh()` if needed. Statements
    run with `session.execute(insert/update/delete)` hit the database at once and need no flush.
  - `.returning()` instead of an extra SELECT; key returned rows by a column (e.g. fingerprint), never by position.
  - Upserts with `pg_insert(...).on_conflict_do_update(...)`.
  - A new repository is added to `UnitOfWorkPort` and `SQLUnitOfWork.__aenter__`.- **External APIs** (Spotify, OpenRouter): DTOs are Pydantic models matching the external shape exactly; standalone mapper
  functions (`to_domain_track(dto) -> Track`) hold the transformations (`providers/spotify/mappers.py`).
- **CLI:**
  - Each Typer command is a thin sync wrapper calling `asyncio.run()` on a co-located `<command>_logic` function
    (never a `_`-prefixed name). A command that must print between two steps runs them in one `asyncio.Runner`
    (`provider/connect.py`): a second `asyncio.run()` fails, as the pooled database connections are bound to the first
    event loop.
  - The callback is `<group>_<command>_command`, its logic `<group>_<command>_logic`, one
    `<group>_<command>_<step>_logic` per step when the command runs several (`provider_connect_start_logic`), with the
    CLI names (dashes become underscores). The group looks redundant inside its module, but a reader skimming a test
    or a search result sees which command it is (`playlist_history_logic`, not `history_logic`), and every name stays
    unique. The decorator always names the command (`@app.command("history")`): without it, Typer would derive
    `playlist-history-command` from the function name.
  - `*_logic` returns data or raises; it never prints. All output (messages, Rich tables) belongs in the
    `@app.command` callback. Exception: interactive prompts that drive the logic mid-loop.
  - Option order: filters (`--force`, `--provider`), then processing config (`--batch-size`), then the cap (`--limit`).

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
`get_taste_profile`). Modules put the object first so that `ls` groups a feature, which also keeps the module name
apart from its function (`user_create.create_user`).

| What | Pattern | Example |
|------|---------|---------|
| Use case module | `<object>_<action>.py`, grouped by object | `ratings_import.py` |
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
- Strict type hints everywhere, tests included. `str | None`; IDs are `uuid.UUID`. No `Any` unless justified.
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
- No docstrings for obvious code; only for ports, complex algorithms and non-obvious `Raises:`. Google style, without
  repeating the types.

## Logging and errors
- `logger = logging.getLogger(__name__)`. Levels: ERROR unrecoverable, WARNING handled but unexpected, INFO milestones
  only, DEBUG flow.
- f-strings are fine for messages. Add `extra={}` when the data is worth querying in an aggregator (IDs, counts).
  In `except` blocks: `logger.exception("Static message", extra={...})`, the traceback carries the detail.
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
