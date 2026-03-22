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
- [ ] Use cases accept Input Schemas (Pydantic), return Domain Entities (dataclasses)
- [ ] Standalone `async def` for simple use cases; class with named method for complex ones

### Infrastructure Layer (`museflow/infrastructure/`)
- [ ] SQLAlchemy models use `MappedAsDataclass + Base`
- [ ] Every SQLAlchemy model implements `to_entity(self) -> Entity`
- [ ] `JSONB` and `ARRAY` imported from `sqlalchemy.dialects.postgresql` (NOT generic SQLAlchemy)
- [ ] Auto-fields (`id`, `created_at`, `updated_at`) use `init=False` + `sort_order` from mixins
- [ ] Repositories inject `AsyncSession` via `__init__`
- [ ] Repositories use SQLAlchemy 2.0 style (`select/update/delete`, not legacy `session.query()`)
- [ ] `.returning()` used on mutations instead of a follow-up SELECT
- [ ] External API adapters define DTOs in `schemas.py` and mappers as standalone functions in `mappers.py`
- [ ] Tenacity adapters: `_is_retryable_error()` explicitly returns `False` for non-retriable exceptions

### Logging
- [ ] No secrets logged (tokens, passwords)
- [ ] Structured context via `extra={}` dict, not f-strings (except in CLI use case logs)
- [ ] `logger.exception()` used inside `except` blocks (not `logger.error()`)

### Naming conventions
- [ ] `*` = domain entity | `*_db` = SQLAlchemy model | `*_in` = Pydantic input | `*_dto` = external DTO

### Tests
- [ ] All test functions, fixtures, and factory classes have strict type annotations
- [ ] `mock.AsyncMock` used for async ports, `mock.Mock` for sync
- [ ] `async_session_db` used by default (not `async_session_trans` unless necessary)
- [ ] No new shared fixtures defined inside test files — they belong in `conftest.py`
- [ ] `__set_relationships__ = False` on SQLAlchemy factories
- [ ] `__allow_none_optionals__ = False` on Pydantic input factories

## Output format

For each violation found:
1. State the file and line number
2. Quote the offending code
3. Explain the violation
4. Suggest the correct fix

If no violations are found, confirm the code is compliant.

After the review, run `make lint` to catch any additional type or style issues.
