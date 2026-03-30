# MuseFlow Project Guidelines

## Stack & Tools
- **Python:** 3.13 managed by `uv`
- **Frameworks:** FastAPI (API), Typer (CLI), SQLAlchemy 2.0 async, Pydantic v2
- **HTTP:** httpx (async), tenacity (retry logic)
- **Formatter/Linter:** Ruff (line length 119), mypy (strict), deptry
- **Test:** pytest + pytest-cov, polyfactory, pytest-httpx, WireMock
- **DB:** PostgreSQL only (uses PostgreSQL-specific features throughout)

## Commands
- `make install` — install deps + pre-commit hooks
- `make lint` — format + type check + dependency check
- `make test` — all tests with 100% branch coverage
- `make test-unit` / `make test-integration` — targeted runs
- `make run` — start FastAPI dev server
- `make db-revision` / `make db-upgrade` — Alembic migrations
- `make up` / `make down` — Docker (DB + WireMock)

## Architecture: Clean / Hexagonal

```
museflow/
├── domain/          # Pure Python — NO framework imports ever
│   ├── entities/    # frozen dataclasses
│   ├── value_objects/
│   ├── services/    # domain services (e.g., TrackReconciler)
│   ├── utils/       # pure functions (text normalization, fingerprinting)
│   ├── exceptions.py
│   └── types.py     # enums and type aliases
├── application/     # Orchestration — depends ONLY on domain
│   ├── use_cases/
│   ├── inputs/      # Pydantic command/input schemas
│   └── ports/       # ABC interfaces (repositories, providers, advisors, security)
└── infrastructure/  # Implements ports
    ├── adapters/
    │   ├── database/
    │   │   ├── models/       # MappedAsDataclass ORM models
    │   │   └── repositories/ # Port implementations
    │   ├── providers/spotify/
    │   └── advisors/lastfm/
    ├── config/settings/      # Pydantic settings (SPOTIFY_, DATABASE_, etc.)
    └── entrypoints/
        ├── api/              # FastAPI routes + dependencies
        └── cli/              # Typer commands + dependencies
```

## Domain Layer

### Entities
```python
@dataclass(frozen=True, kw_only=True)
class Track(BaseMediaItem):
    fingerprint: str = ""

    def __post_init__(self) -> None:
        super().__post_init__()
        # Permanent computed fields: use object.__setattr__ (frozen dataclass workaround)
        if not self.fingerprint:
            object.__setattr__(self, "fingerprint", generate_fingerprint(...))
```
- NO framework imports. Never enforce DB limits (varchar lengths) here.
- Business rules and validation only in `__post_init__`.
- **Computed permanent fields** (fingerprint, normalized genres): compute in `__post_init__` via `object.__setattr__`.
- **Dynamic fields**: use `@property`.
- External IDs/slugs passed in from the mapper — NOT generated in the entity.

### Ports (Interfaces)
```python
class UserRepository(ABC):
    @abstractmethod
    async def get_by_id(self, user_id: uuid.UUID) -> User | None: ...
```
- Use `abc.ABC` + `@abstractmethod`. Accept Input Schemas, return Domain Entities.

## Application Layer (Use Cases)

**Default — standalone async function:**
```python
async def user_create(
    user_in: UserCreateInput,
    user_repository: UserRepository,
    password_hasher: PasswordHasherPort,
) -> User:
    ...
```

**Complex — class with named method (when injected state is needed):**
```python
class ImportStreamingHistoryUseCase:
    def __init__(self, provider_library: ProviderLibraryPort, track_repository: TrackRepository) -> None:
        self._provider_library = provider_library
        self._track_repository = track_repository

    async def import_history(self, user: User, config: ImportStreamingHistoryConfigInput) -> ImportStreamingHistoryReport:
        ...
```
- Accept ports via parameters (DI). NEVER instantiate repositories inside use cases.
- Accept Input Schemas, return Domain Entities (dataclasses). Input Schemas can be Pydantic `BaseModel` **or** `@dataclass(frozen=True, kw_only=True)` — both are valid.
- Use a class only when the use case holds injected dependencies and is called with user-specific args.

## Infrastructure Layer

### SQLAlchemy Models (PostgreSQL only)
```python
from sqlalchemy.dialects.postgresql import ARRAY, JSONB  # Always from postgresql dialect

class Track(MusicItemMixin, Base, kw_only=True):
    __tablename__ = "museflow_track"

    fingerprint: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    artists: Mapped[list[ArtistDict]] = mapped_column(JSONB, nullable=False, default_factory=list)
    genres: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default_factory=list)

    def to_entity(self) -> TrackEntity:
        return TrackEntity(id=self.id, name=self.name, ...)
```
- Use `MappedAsDataclass + Base`. Always implement `to_entity(self) -> Entity`.
- Auto-fields (`id`, `created_at`, `updated_at`) come from mixins: `init=False` + `sort_order`.
- Use `JSONB` for nested structures (from `sqlalchemy.dialects.postgresql`).
- Use `ARRAY(String)` for string lists (from `sqlalchemy.dialects.postgresql`).
- Use `@declared_attr` for dynamic `__table_args__` in mixins (UniqueConstraint, Index).

### Repositories
```python
class UserSQLRepository(UserRepository):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        stmt = select(UserModel).where(UserModel.id == user_id)
        result = await self.session.execute(stmt)
        user_db = result.scalar_one_or_none()
        return user_db.to_entity() if user_db else None
```
- Inject `AsyncSession`. Use `select/update/delete` (SQLAlchemy 2.0 style, no legacy).
- `.scalar_one_or_none()` for optional, `.scalar_one()` for required.
- `.returning()` on updates/deletes to avoid extra SELECT round-trip.
- `await self.session.commit()` then `await self.session.refresh(obj)` after mutations.
- Use `pg_insert(...).on_conflict_do_update(...)` for upserts (PostgreSQL-specific).

### External API Adapters (Spotify, Last.fm)
- **DTOs**: Pydantic models matching the external API shape exactly.
- **Mappers**: Standalone functions `to_domain_track(dto: SpotifyTrack) -> Track`. Complex transformations (fingerprinting, normalization) live here.

## Naming Conventions
| Suffix | Meaning | Type |
|--------|---------|------|
| `user` | Domain Entity | frozen dataclass |
| `user_db` | SQLAlchemy Model | MappedAsDataclass |
| `user_in` | Input Schema (command) | Pydantic BaseModel |
| `user_dto` | External API DTO | Pydantic BaseModel |

## Types & Style
- 100% strict type hints everywhere — including tests. Native union: `str | None`. IDs: `uuid.UUID`.
- No `Any` unless justified. Ruff line length: 119.
- Async everywhere: FastAPI, SQLAlchemy, httpx.

## Logging
```python
logger = logging.getLogger(__name__)

# f-strings are always allowed — they produce the human-readable message
# Add extra={} when the data is useful for an aggregator or dashboard
logger.info(f"Seed tracks: {len(track_seeds)}", extra={"count": len(track_seeds)})
logger.warning(f"Track not reconciled: '{track}'", extra={"track": str(track), "user_id": str(user.id)})

# Exception blocks — static message + extra (traceback carries the error detail; no f-string needed)
logger.exception("Spotify API error", extra={"status_code": e.response.status_code})
```
- Levels: ERROR (unrecoverable), WARNING (handled unexpected), INFO (milestones, minimal), DEBUG (flow).
- NEVER log secrets (tokens, passwords). Log IDs only.
- f-strings: always OK for the message — **never** for secrets.
- `extra={}`: add when the data would be useful to query in an aggregator (IDs, counts, entity names). Not required for every f-string — use judgement.
- Exception blocks: static message + `extra={}`. No f-string needed; the traceback carries the error.
- `logger.debug()` — f-string only is fine; `extra` optional.

## Error Handling
- Domain exceptions live in `museflow/domain/exceptions.py` — use these across all layers.
- Infrastructure-specific exceptions (e.g., `SpotifyTokenExpiredError`) live in their adapter package.
- In tenacity retry adapters, `_is_retryable_error()` must explicitly `return False` for all non-retriable exceptions.

## Documentation
- No docstrings for obvious functions. Only for: public ports/ABCs, complex algorithms, non-obvious `Raises:`.
- Format: Google Style. Don't duplicate types from the signature.

## Testing

### Philosophy
Tests are the **contract with our users**. They must be clean, clear, and easy to maintain — not just achieve 100% coverage. Poorly written tests are worse than no tests: they create a false sense of security and make refactoring painful.

- **100% branch coverage** is mandatory (`pytest-cov --cov-branch --cov-fail-under=100`).
- **Integration tests** are the primary focus — test full flows with a real DB and WireMock for external APIs.
- **Unit tests** fill gaps — complex domain logic and edge cases hard to reach via integration.
- **Do not mirror happy paths**: if a happy path is already covered by an integration test, do not add a unit test for the same flow — it creates maintenance duplication with no extra confidence.
- **Use `AsyncMock` for repositories**: do not implement fake (in-memory) repositories. `AsyncMock` is appropriate here: complex repository methods (filtering, bulk upsert) are hard to fake correctly, and integration tests already validate the port contract.
- **All test code is typed** — fixtures, test functions, factories, helpers all have strict type annotations.

### Test File Mirror
```
museflow/application/use_cases/user_create.py
→ tests/unit/application/use_cases/test_user_create.py
→ tests/integration/application/use_cases/test_user_create.py
```

### Fixture Scoping Strategy
Fixtures are organized in `conftest.py` files at each directory level. Scope is chosen carefully:

```
tests/conftest.py          # scope="session": anyio_backend, configure_logging, frozen_time
tests/integration/conftest.py
    scope="session":  test_db_name, create_test_database, async_engine  (DB lifecycle — run once)
    scope="function": async_session_db (autouse=True, auto-rollback), async_session_trans
tests/unit/conftest.py     # scope="function" (default): all mocks, entity fixtures
tests/.../conftest.py      # Nested conftest for area-specific shared fixtures
```

Rules:
- Use `scope="session"` for expensive, shared setup (DB engine, test DB creation, logging).
- Use `scope="function"` (default) for everything that touches state.
- Use `autouse=True` sparingly — only for fixtures that EVERY test in that scope needs (e.g., DB rollback).
- Use `request.param` on fixtures for parametrization via `@pytest.mark.parametrize` on the fixture itself.

### Unit Tests
```python
class TestUserCreateUseCase:
    async def test__nominal(
        self,
        user_create_data: UserCreateInput,      # factory-built Pydantic input
        mock_user_repository: mock.AsyncMock,   # from conftest
        mock_password_hasher: mock.Mock,        # from conftest
    ) -> None:
        mock_user_repository.get_by_email.return_value = None
        user = await user_create(user_create_data, mock_user_repository, mock_password_hasher)
        assert user.email == user_create_data.email
```
- Use `mock.AsyncMock` for async repositories/ports, `mock.Mock` for sync ports.
- Use factory-built entities from `tests/unit/factories/`.

### Integration Tests
```python
class TestUserCreateUseCase:
    async def test__nominal(
        self,
        async_session_db: AsyncSession,        # real DB, auto-rollback
        user_repository: UserRepository,       # real SQLRepository
        password_hasher: PasswordHasherPort,   # real Argon2
    ) -> None:
        user = await user_create(user_create_data, user_repository, password_hasher)
        stmt = select(UserModel).where(UserModel.id == user.id)
        user_db = (await async_session_db.execute(stmt)).scalar_one_or_none()
        assert user_db is not None
```
- Use `async_session_db` (auto-rollback, autouse) by default — fast and isolated.
- Use `async_session_trans` ONLY when testing code that explicitly commits — slower, uses TRUNCATE.

### Factories
```python
# Domain entities — DataclassFactory
class UserFactory(DataclassFactory[User]):
    __model__ = User

# Pydantic inputs — ModelFactory
class UserCreateInputFactory(ModelFactory[UserCreateInput]):
    __model__ = UserCreateInput
    __allow_none_optionals__ = False   # Don't generate None for optional fields

# SQLAlchemy models — SQLAlchemyFactory (integration tests only)
class UserModelFactory(BaseModelFactory[User]):
    __model__ = User
    email = Use(BaseModelFactory.__faker__.email)

    @post_generated
    @classmethod
    def hashed_password(cls) -> str:
        return get_password_hasher().hash("testtest")
```
- `DataclassFactory` → domain entities | `ModelFactory` → Pydantic | `SQLAlchemyFactory` → DB models.
- `__set_relationships__ = False` on all SQLAlchemy factories (conflicts with `MappedAsDataclass`).
- `__use_defaults__ = True` and `__set_as_default_factory_for_type__ = True` on base model factory.
- `__allow_none_optionals__ = False` on input factories when you always want values.
- Use `@post_generated` for fields that depend on other generated fields.
- Use `Use(faker.email)` for realistic field values.

### Assertion Style
```python
# Prefer direct comparison — concise and clear
assert items == expected_items

# If you must loop, include an identifier for debuggability
for i, item in enumerate(items):
    assert item.active, f"Item {i} (id={item.id}) failed"
```

### WireMock (External APIs)
- Spotify/Last.fm API responses are mocked via WireMock in integration tests.
- Stub files live in `tests/assets/wiremock/spotify/` and `tests/assets/wiremock/lastfm/`.
- Use the `spotify_wiremock` fixture to configure stubs per-test.

### Dead End Protocol

When fixing a failing test or external-tool issue, Claude applies a **3-attempt cap**. If the problem is not resolved after 3 attempts, Claude **stops** iterating and outputs a structured summary instead.

**What counts as one attempt:**
- Run the test(s), observe the failure.
- Form a hypothesis, apply a targeted fix (edit a file, update a stub, change a fixture).
- Re-run to verify.

**When the cap is reached, output:**

```
## Dead End — <test or file name>

### Attempts (3/3)
1. **Attempt 1:** <what was changed> → <error / result>
2. **Attempt 2:** <what was changed> → <error / result>
3. **Attempt 3:** <what was changed> → <error / result>

### Root Cause
<Clear, honest assessment of what the problem appears to be and why it is hard to fix automatically.>

### Options
**A — <most likely fix>**
<Concrete steps. Who needs to do what.>

**B — <alternative approach>**
<Concrete steps.>

**C — Skip temporarily**
Mark with `@pytest.mark.skip(reason="<issue>: <short description>")` until the root cause is resolved.
```

**Failure-mode option menus (use as starting point):**

| Failure mode | Typical options |
|---|---|
| Test assertion keeps failing | A) Fix source bug · B) Update test expectation · C) Skip |
| WireMock stub mismatch | A) Update stub JSON · B) Add `@pytest.mark.wiremock` · C) Regenerate stub from real API (`--spotify-live`) |
| DB / fixture error | A) Run `make db-upgrade` · B) Fix conftest fixture chain · C) Restart Docker (`make down && make up`) |
| External library break | A) Pin previous version in `pyproject.toml` · B) Adapt code to new API · C) Skip + open issue |

### Special Markers
- `@pytest.mark.slow` — skipped by default, run with `--slow`
- `@pytest.mark.spotify_live` — requires `--spotify-refresh-token`, hits real Spotify API

## Claude

### Slash Commands (`.claude/commands/`)
Reusable prompts invoked with `/command-name`:

| Command | Purpose |
|---|---|
| `/new-feature` | Scaffold a full feature across all layers |
| `/new-provider` | Scaffold a new music provider integration |
| `/new-migration` | Generate and review an Alembic migration |
| `/add-tests` | Add tests for a source file to 100% branch coverage |
| `/arch-review` | Review changed files for Clean Architecture violations |
| `/security-review` | Review changed files for security vulnerabilities |

### Agents (`.claude/agents/`)
Autonomous subagents invoked with `/agent:name` or auto-routed by Claude:

| Agent | Purpose |
|---|---|
| `python` | Fix lint errors autonomously — runs `make lint`, fixes ruff/mypy/deptry issues, iterates until clean |
| `test` | Fix failing tests and fill coverage gaps — runs `make test`, traces failures, writes missing branches |
| `arch` | Architecture compliance review — checks all changed files against hexagonal architecture rules |
| `security` | Security review — checks changed files for vulnerabilities, runs `uv audit` for CVEs |
| `engineer` | Read-only codebase explorer — explains feature flows, locates code, guides implementation approach |
