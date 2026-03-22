# New Feature Scaffold

You are scaffolding a new feature for the MuseFlow project, following strict Clean Architecture conventions defined in CLAUDE.md and CONVENTIONS.md.

The feature name is: **$ARGUMENTS**

## What to build

Create ALL of the following layers (skip a layer only if it clearly doesn't apply — e.g., no API endpoint for a background-only feature):

### 1. Domain Entity — `museflow/domain/entities/<name>.py`
- `@dataclass(frozen=True, kw_only=True)`
- Business rules in `__post_init__` only
- Computed permanent fields (e.g., fingerprints) via `object.__setattr__`
- Dynamic fields as `@property`
- NO framework imports

### 2. Domain Exceptions — `museflow/domain/exceptions.py`
- Add any new domain exceptions the feature requires

### 3. Input Schema — `museflow/application/inputs/<name>.py`
- Pydantic `BaseModel` with strict validation
- Named `[Entity]CreateInput`, `[Entity]UpdateInput`, `[Entity]FilterInput` as needed

### 4. Port (Interface) — `museflow/application/ports/repositories/<name>.py` or `museflow/application/ports/providers/<name>.py`
- `abc.ABC` with `@abstractmethod`
- Accept Input Schemas, return Domain Entities

### 5. Use Case — `museflow/application/use_cases/<name>.py`
- **Default**: standalone `async def` function
- **Complex** (needs injected state): class with named method
- Accept ports via parameters — NEVER instantiate repositories inside
- Accept Input Schemas, return Domain Entities

### 6. SQLAlchemy Model — `museflow/infrastructure/adapters/database/models/<name>.py`
- `MappedAsDataclass + Base`, `kw_only=True`
- Use mixins: `UUIDIdMixin`, `DatetimeTrackMixin`
- `JSONB`, `ARRAY` from `sqlalchemy.dialects.postgresql`
- Implement `to_entity(self) -> Entity`
- Add `__table_args__` with appropriate constraints/indexes

### 7. Repository Implementation — `museflow/infrastructure/adapters/database/repositories/<name>.py`
- Implement the port
- Inject `AsyncSession`
- SQLAlchemy 2.0 style: `select/update/delete`
- `.scalar_one_or_none()` / `.scalar_one()`
- `.returning()` on mutations
- `commit()` then `refresh()` after writes

### 8. API Endpoint — `museflow/infrastructure/entrypoints/api/v1/endpoints/<name>.py`
- FastAPI router with proper response models
- Wire up dependencies via `museflow/infrastructure/entrypoints/api/dependencies.py`

### 9. CLI Command — `museflow/infrastructure/entrypoints/cli/commands/<name>/`
- Typer command group
- Wire up dependencies via `museflow/infrastructure/entrypoints/cli/dependencies.py`

### 10. Alembic Migration
- Remind the user to run `make db-revision` after models are created

## Tests to create

### Unit Tests
- `tests/unit/factories/entities/<name>.py` — `DataclassFactory` for the entity
- `tests/unit/factories/inputs/<name>.py` — `ModelFactory` for input schemas
- `tests/unit/application/use_cases/test_<name>.py` — test use case with mocks
- `tests/unit/infrastructure/adapters/database/repositories/test_<name>.py` (if needed)

### Integration Tests
- `tests/integration/factories/models/<name>.py` — `SQLAlchemyFactory` for DB model
- `tests/integration/application/use_cases/test_<name>.py` — full flow with real DB
- `tests/integration/infrastructure/entrypoints/api/v1/endpoints/test_<name>.py`
- `tests/integration/infrastructure/entrypoints/cli/commands/test_<name>.py`

## Conventions reminders

- Naming: `entity` (domain), `entity_db` (SQLAlchemy), `entity_in` (Pydantic input), `entity_dto` (external DTO)
- 100% branch coverage is mandatory — test every `if/else` path
- All test code must be strictly typed
- Use `mock.AsyncMock` for async ports, `mock.Mock` for sync ports
- Use `async_session_db` fixture (auto-rollback) in integration tests by default
- Add shared fixtures to the appropriate `conftest.py` level
- `JSONB`/`ARRAY` always from `sqlalchemy.dialects.postgresql`
- After scaffolding, run `make lint` and `make test`

## Execution

Start by asking any clarifying questions if the feature name is ambiguous (e.g., does it need an API endpoint? a CLI command?). Then scaffold all applicable layers, stating clearly which ones you're skipping and why.
