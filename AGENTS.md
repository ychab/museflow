# MuseFlow agent guidelines

The single instruction file for coding agents. Claude Code reads it natively: never add a `CLAUDE.md` or
`CLAUDE.local.md`, which would replace it. Testing rules live in `tests/AGENTS.md`, loaded when working under `tests/`.
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
CLI help, tests, commit messages, PR descriptions, plans and docs.

## Architecture: Clean / Hexagonal

```
museflow/
├── domain/          # Pure Python — NO framework imports ever
│   ├── entities/    # frozen dataclasses
│   ├── value_objects/
│   ├── services/    # domain services (e.g., Reconciler)
│   ├── utils/       # pure functions (text normalization, fingerprinting, locale validation)
│   ├── exceptions.py
│   ├── enums.py     # all StrEnum / IntFlag definitions
│   ├── const.py     # all domain constants
│   └── types.py     # type aliases only
├── application/     # Orchestration — depends ONLY on domain
│   ├── use_cases/
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
- **Inputs** are Pydantic `BaseModel` or `@dataclass(frozen=True, kw_only=True)`, named `<Entity><Action>Input` or
  `<Feature>ConfigInput`.
- **Use cases** are standalone async functions by default (`use_cases/user_create.py`). Use a class with a named method
  only when it holds injected dependencies and is called with user-specific args (`use_cases/history_import.py`).
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
  - `MappedAsDataclass` + `Base`; `id`, `created_at`, `updated_at` come from mixins (`init=False`).
  - Always both `from_entity(cls, entity)` and `to_entity(self)`, symmetric. Repositories build rows with
    `from_entity`, never field by field.
  - `JSONB` and `ARRAY(String)` from `sqlalchemy.dialects.postgresql`; `@declared_attr` for dynamic `__table_args__`.
- **Repositories** (canonical: `database/repositories/users.py`):
  - Take an `AsyncSession`; SQLAlchemy 2.0 `select/update/delete`; `.scalar_one_or_none()` / `.scalar_one()`.
  - **Never commit**: `flush()` after mutations (then `refresh()` if needed). The unit of work commits.
  - `.returning()` instead of an extra SELECT; key returned rows by a column (e.g. fingerprint), never by position.
  - Upserts with `pg_insert(...).on_conflict_do_update(...)`.
  - A new repository is added to `UnitOfWorkPort` and `SQLUnitOfWork.__aenter__`.
- **External APIs** (Spotify, OpenRouter): DTOs are Pydantic models matching the external shape exactly; standalone mapper
  functions (`to_domain_track(dto) -> Track`) hold the transformations (`providers/spotify/mappers.py`).
- **CLI:**
  - Each Typer command is a thin sync wrapper calling `asyncio.run()` on a co-located `<command>_logic` function
    (never a `_`-prefixed name).
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

## Types & style
- Strict type hints everywhere, tests included. `str | None`; IDs are `uuid.UUID`. No `Any` unless justified.
- A signature fits on one line, or has one parameter per line with a trailing comma; never all parameters together on
  one indented line.
- Parameters grouped by role: inputs first, then the unit of work, then other ports. DI parameters stay contiguous;
  a new port goes next to the others, never at the end.
- No single-letter names, except in comprehensions, lambdas, loop indexes and `except ... as e`.
- Group module members by kind (private functions, then classes); never class/function/class.
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
- In tenacity adapters, `_is_retryable_error()` explicitly returns `False` for every non-retryable exception.
- No `assert` in production code (Ruff S101): raise `ValueError` at the top of the function for contract violations;
  where mypy can't narrow after the guard, use `# type: ignore[union-attr]` at the call site.

## Testing
100% branch coverage; integration tests first, unit tests for error paths. Full rules: `tests/AGENTS.md`.

**Dead End Protocol:** after 3 failed attempts to fix the same problem, stop and report options A/B/C instead of
looping.
