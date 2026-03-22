# Architecture Compliance Review

You are reviewing changed MuseFlow code for Clean Architecture violations.

## What to review

If `$ARGUMENTS` is provided, review only those files. Otherwise, review all files changed since the last commit:
```bash
git diff --name-only HEAD
```

Read each changed file and check for the violations below.

## Checklist

### Domain Layer (`museflow/domain/`)
- [ ] No framework imports (`fastapi`, `sqlalchemy`, `pydantic`, `httpx`, etc.)
- [ ] All entities use `@dataclass(frozen=True, kw_only=True)`
- [ ] Business rules enforced in `__post_init__` only — no DB constraints (varchar lengths, etc.)
- [ ] Computed permanent fields use `object.__setattr__` in `__post_init__`
- [ ] Dynamic fields use `@property`
- [ ] No external IDs/slugs generated inside entities (belongs in mappers)
- [ ] All ports use `abc.ABC` + `@abstractmethod`

### Application Layer (`museflow/application/`)
- [ ] Use cases NEVER instantiate repositories directly — only accept them as parameters
- [ ] Use cases depend ONLY on domain (no infrastructure imports)
- [ ] Use cases accept Input Schemas, return Domain Entities (dataclasses). Input Schemas can be either Pydantic `BaseModel` **or** `@dataclass(frozen=True, kw_only=True)` — both are valid. Flag dataclass inputs only if they are missing `kw_only=True`.
- [ ] Standalone `async def` for simple use cases; class with named method for complex ones

### Infrastructure Layer (`museflow/infrastructure/`)
- [ ] SQLAlchemy models use `MappedAsDataclass + Base`
- [ ] Every SQLAlchemy model implements `to_entity(self) -> Entity`
- [ ] `JSONB` and `ARRAY` imported from `sqlalchemy.dialects.postgresql` (NOT generic SQLAlchemy)
- [ ] Auto-fields (`created_at`, `updated_at`) use `init=False` + `sort_order` from mixins. `DatetimeTrackMixin` is expected on most models but may be omitted when the model already has a domain-specific timestamp that covers the same need (e.g. `token_expires_at` on auth token models).
- [ ] `UUIDIdMixin.id` intentionally keeps `init=True` (no `init=False`) so that upserts can pass a known UUID to the constructor. Do NOT flag this as a violation.
- [ ] Repositories inject `AsyncSession` via `__init__`
- [ ] Repositories use SQLAlchemy 2.0 style (`select/update/delete`, not legacy `session.query()`)
- [ ] `.returning()` used on mutations instead of a follow-up SELECT
- [ ] External API adapters define DTOs in `schemas.py` and mappers as standalone functions in `mappers.py`
- [ ] Tenacity adapters: `_is_retryable_error()` explicitly returns `False` for non-retriable exceptions

### Logging
- [ ] No secrets logged (tokens, passwords)

The logging rules below apply to **operator logs** (`logger = logging.getLogger(__name__)`):
- [ ] `logger.exception()` used inside `except` blocks (not `logger.error()`) — attaches traceback automatically
- [ ] Static messages with structured context via `extra={}` — never f-strings
- [ ] `logger.debug()` is exempt from the f-string rule — do NOT flag it

**Domain layer exception:** domain services (`museflow/domain/`) cannot import `get_cli_logger` (infrastructure import = arch violation). If a domain service log is user-facing (e.g. reconciliation warnings displayed in CLI output), use the standard `logger` with an f-string **and** `extra={}` keys. Do NOT flag f-strings in `museflow/domain/` at warning/error level if `extra={}` is present.

**User-facing CLI logs** (infrastructure and above) must use `cli_logger = get_cli_logger(__name__)` (from `museflow.infrastructure.config.loggers`), never the standard `logger`:
- [ ] `cli_logger.*` calls **may use f-strings** — do NOT flag them
- [ ] `cli_logger.exception()` inside `except` blocks — attaches traceback to the log record for aggregators; the plain `%(message)s` formatter hides it from the CLI user. Do NOT flag it.
- [ ] `cli_logger` at **warning/error level** should include `extra={}` keys (excluding `"error"` — already covered by the attached exception) for observability
- [ ] If a file has f-string log calls on `logger.*`, that is a violation — flag it
- [ ] If a file declares `cli_logger`, verify it uses `get_cli_logger(__name__)`, not `logging.getLogger`

### Naming conventions
- [ ] `*` = domain entity | `*_db` = SQLAlchemy model | `*_in` = Pydantic input | `*_dto` = external DTO

### Tests
- [ ] All test functions, fixtures, and factory classes have strict type annotations
- [ ] `mock.AsyncMock` used for async ports, `mock.Mock` for sync
- [ ] `async_session_db` used by default (not `async_session_trans` unless necessary)
- [ ] No new shared fixtures defined inside test files — they belong in `conftest.py`
- [ ] `__set_relationships__ = False` on SQLAlchemy factories
- [ ] `__allow_none_optionals__ = False` on Pydantic **Update** input factories (forces all optional fields to real values so bulk-update tests exercise every field). **Create** factories typically have no optional fields so this flag is not needed there — do not flag its absence on Create factories.

## Output format

For each violation found:
1. State the file and line number
2. Quote the offending code
3. Explain the violation
4. Suggest the correct fix

If no violations are found, confirm the code is compliant.

After the review, run `make lint` to catch any additional type or style issues.
