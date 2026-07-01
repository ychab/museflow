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
│   ├── services/    # domain services (e.g., Reconciler)
│   ├── utils/       # pure functions (text normalization, fingerprinting, locale validation)
│   ├── exceptions.py
│   ├── enums.py     # all StrEnum / IntFlag definitions
│   ├── const.py     # all domain constants (score bounds, GENRE_*_TAGS tuples)
│   └── types.py     # type aliases only (TrackOrdering, ScoreAdvisor, LocaleCode, …)
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
    │   └── advisors/gemini/
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
    user_in: UserCreateInput,           # inputs first
    user_repository: UserRepository,    # repositories next
    password_hasher: PasswordHasherPort, # other ports last
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

    @classmethod
    def from_entity(cls, entity: TrackEntity) -> "Track":
        return cls(id=entity.id, name=entity.name, ...)

    def to_entity(self) -> TrackEntity:
        return TrackEntity(id=self.id, name=self.name, ...)
```
- Use `MappedAsDataclass + Base`. Always implement both `from_entity(cls, entity) -> Model` and `to_entity(self) -> Entity` — they are symmetric: `from_entity` maps domain → DB, `to_entity` maps DB → domain. Repositories use `from_entity` to build DB objects; never instantiate models field-by-field in a repository.
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

### External API Adapters (Spotify, Gemini)
- **DTOs**: Pydantic models matching the external API shape exactly.
- **Mappers**: Standalone functions `to_domain_track(dto: SpotifyTrack) -> Track`. Complex transformations (fingerprinting, normalization) live here.

### CLI Entrypoints
- Each Typer command is a thin sync wrapper that calls `asyncio.run()` on a co-located async function.
- Name the async helper `<command>_logic` (e.g. `add_artists_logic`, `purge_logic`) — never a `_`-prefixed private name.
- **Output belongs in the callback, not the logic function.** The `*_logic` function is pure orchestration — it returns data, raises exceptions, and never calls `typer.secho`, `typer.echo`, `console.print`, or similar. The `@app.command` callback owns all user-visible output: success messages, empty-state notices, Rich tables. Exception: interactive prompts (`typer.confirm`, `typer.prompt`) that *drive* the logic flow mid-loop may stay in the logic function.
- **CLI option ordering:** filters first (e.g. `--force`, `--provider`), then processing config (e.g. `--batch-size`), then cap (`--limit`).

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
- **Group function parameters by logical role** — input schemas first, then repositories, then other ports (providers, advisors, hashers). Keep each group contiguous. Callers use keyword args, so order is documentation, not necessity.
- **In use case functions and class constructors, DI parameters (repositories + ports) must be contiguous.** Never scatter a port between operation flags or domain inputs — if a port is added later, insert it next to the other DI params, not at the end of the signature.

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
- **Never use `assert` in production code.** For programmer-contract violations (e.g. a caller passing `None` for a required argument), raise `ValueError` at the top of the function. Where mypy cannot narrow the type after such a guard, use `# type: ignore[union-attr]` at the call site rather than adding an inline `assert`.

## Documentation
- No docstrings for obvious functions. Only for: public ports/ABCs, complex algorithms, non-obvious `Raises:`.
- Format: Google Style. Don't duplicate types from the signature.

## Testing

### Philosophy
Tests are the **contract with our users** — clean, clear, easy to maintain, not just 100% coverage.

- **100% branch coverage** is mandatory.
- **Integration tests** are the primary focus — full flows with a real DB and WireMock.
- **Unit tests** fill gaps — error branches and edge cases hard to reach via integration.
- **Do not mirror happy paths** — if integration covers the nominal flow, no unit test for the same.
- **Error paths belong in unit tests** — use `AsyncMock` repositories, not an integration test.
- **No fake (in-memory) repositories** — use `AsyncMock`.
- **All test code is typed** — fixtures, functions, factories, helpers.
- **No inner imports in test functions** — all imports at module level.

### Test File Mirror
One test file per source file — never consolidate:
```
museflow/application/use_cases/user_create.py
→ tests/unit/application/use_cases/test_user_create.py
→ tests/integration/application/use_cases/test_user_create.py
```

### Fixture Rules
- `scope="session"` for expensive shared setup (DB engine, test DB, logging).
- `scope="function"` (default) for everything that touches state.
- `autouse=True` only for fixtures every test in scope needs.
- `request.param` for parametrized fixtures — never module-level `_make_*` helpers.
- `async_session_db` (auto-rollback) by default; `async_session_trans` only for explicit commit testing.
- **Never `with mock.patch(...)` inside a test method** — always a `pytest.fixture` instead.

### CLI Command Tests
Each command: 3 unit classes (`TestXParserCommand`, `TestXCommand`, `TestXLogic`) + 1 integration `TestXLogic` (happy-path only). Canonical: `tests/unit/infrastructure/entrypoints/cli/commands/users/test_update.py`.

### Factories
- `DataclassFactory` → domain entities | `TypedDictFactory` → TypedDicts | `ModelFactory` → Pydantic | `SQLAlchemyFactory` → DB models.
- Never create module-level helper functions (`_make_*`, `_build_*`) — call factory directly or use a fixture.

### Dead End Protocol
After 3 failed fix attempts on the same problem, stop and report structured options A/B/C. Full template in the `test` agent.

### Special Markers
- `@pytest.mark.slow` — skipped by default, run with `--slow`
- `@pytest.mark.spotify_live` — requires `--spotify-refresh-token`, hits real Spotify
- `@pytest.mark.wiremock` — required on any integration class using WireMock (prevents xdist flakiness)
