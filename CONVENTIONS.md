# MuseFlow Coding Conventions & Architecture

## 1. Architecture Overview
This project follows **Clean Architecture (Hexagonal)** principles.
- **Domain (`museflow/domain`)**:
  - **Entities**: Pure Python Dataclasses (`frozen=True`). Represent the "Truth" of the system.
  - **Schemas**: Pydantic Models. Represent "Input/Output" contracts (DTOs, Commands).
  - **Ports**: Interfaces (`abc.ABC`).
- **Application (`museflow/application`)**: Orchestrates business logic. Depends ONLY on Domain.
- **Infrastructure (`museflow/infrastructure`)**: Implements details (SQLAlchemy, FastAPI, Typer CLI commands, Spotify Client, etc).

## 2. Coding Rules by Layer

### Domain Layer

#### A. Entities (`museflow/domain/entities/`)
- **Technology**: Standard Python `@dataclass(frozen=True, kw_only=True)`.
  - **Immutability**: Entities are read-only after creation.
  - **Validation**:
    - **Business Rules ONLY**: Use `__post_init__` to enforce logical consistency (e.g., `start_date < end_date`).
    - **No Tech Constraints**: Do NOT enforce DB limits (e.g., `varchar(255)`) here.
  - **Computed Fields**: Use `__post_init__` with `object.__setattr__` for permanent computed fields, or `@property` for dynamic ones.
  - **Slugs/UUIDs**: Should be treated as plain strings/UUIDs passed in during construction. Logic for generating them belongs in the Adapter/Mapper, not the Entity itself.

#### B. Input Schemas / Commands (`museflow/domain/schemas/`)
- **Technology**: `pydantic.BaseModel` (v2).
- **Purpose**: Define data entering the domain (e.g., `UserCreate`, `UserUpdate`, `TrackFilter`).
- **Validation**: Strict validation (Length, Regex, Enums) happens here.
- **Naming**: `[Entity]Create`, `[Entity]Update`, `[Entity]Filter`.

#### C. Ports (`museflow/domain/ports/`)
- **Technology**: Abstract Base Classes (`abc.ABC`).
- **Signatures**:
  - Accept **Schemas** as input arguments (e.g., `create(data: UserCreate)`).
  - Return **Entities** as output (e.g., `-> User`).

### Application Layer (Use Cases)
- **Structure**:
  - **Default**: Standalone **async functions** (e.g., `async def user_create(...) -> User`).
  - **Complex**: Use a **Class** with `__call__` or `execute` method if state/refactoring is needed.
- **Flow**:
  1. Accept **Schemas** (Pydantic) from the API/Controller.
  2. Call Ports (Repositories).
  3. Return **Entities** (Dataclasses).
- **Dependency Injection**: Accept Ports as arguments. DO NOT instantiate repositories inside use cases.

### Infrastructure Layer

#### A. Database (SQLAlchemy 2.0)
- **Models**:
  - Separate SQLAlchemy models (`MappedAsDataclass` + `Base`).
  - Use `Enum` types directly in columns.
- **Mapping (DB <-> Domain)**:
  - **To Entity**: Implement `to_entity(self) -> Entity` method on the SQLAlchemy Model.
  - **To DB**: Use helper `_entity_to_db_dict` in repositories to handle `dataclasses.asdict` + Enum/JSON conversion.
- **Transactions**:
  - Use `async_session.begin()` or context managers for atomicity.
  - Repositories should accept an `AsyncSession`.

#### B. External APIs (Spotify, etc.)
- **DTOs**: Define Pydantic models matching the *external* API shape exactly.
- **Mapping (DTO <-> Domain)**:
  - Use **standalone Mapper functions** (e.g., `to_domain_track(dto: SpotifyTrack) -> Track`).
  - **Logic**: Complex transformation rules (like slug generation from title) belong here.

## 3. General Python Standards
- **Python Version**: Target **Python 3.13**.
- **Formatting**: Ruff (Line length 119).
- **Typing**:
  - **Strict Type Hints** for ALL arguments and return values.
  - Use native union syntax: `str | None`.
  - Use `uuid.UUID` for IDs.
- **Naming**:
  - `user` = Domain Entity (Dataclass)
  - `user_db` = SQLAlchemy Model
  - `user_in` = Input Schema (Pydantic)
  - `user_dto` = External API DTO

## 4. Documentation & Comments

### Philosophy: "Signal over Noise"
- **Code is the Documentation**: Use descriptive variable/function names and strict type hints first.
- **Avoid Redundancy**: Do NOT write docstrings that just repeat the function name or signature.
  - **Bad**: `def get_user(id): """Gets the user by id."""`
  - **Good**: `def get_user(id): ...` (No docstring needed if obvious)
- **Target Audience**: Write docstrings for **Public Interfaces** (Ports, Abstract Classes) and **Complex Logic** (Algorithms, Regex) where the "Why" or "How" isn't obvious from the code itself.

### Style Guide
- **Format**: **Google Style**.
- **Type Hints**: **Do NOT duplicate types** in the docstring. The function signature is the source of truth for types.
- **Content**: Focus on:
  - **Behavior**: What does it do that isn't obvious?
  - **Arguments**: Only if their purpose isn't clear (e.g., flags, specific formats).
  - **Returns**: What does it return? (e.g., "None if user not found").
  - **Raises**: Crucial! Document exceptions that the caller must handle.

#### Example
```python
def calculate_score(track: Track, user_weight: float = 1.0) -> float:
    """
    Computes the relevance score based on listening history and user preference.

    Args:
        user_weight: Multiplier for user-specific affinity (default 1.0).
                     Values > 1.0 boost the score for favorite genres.

    Returns:
        A normalized score between 0.0 and 100.0.

    Raises:
        ValueError: If user_weight is negative.
    """
    ...
```

## 5. Testing Strategy

### Philosophy
- **Coverage Goal**: **100% Branch Coverage (or Nothing)**.
  - Every `if/else`, loop, and exception path must be tested.
  - Use `pytest-cov` with `--cov-fail-under=100` to enforce this in CI.
- **Integration Tests (`tests/integration`)**: **Primary Focus.**
  - Test full flows (DB + API).
  - Mock external APIs (Spotify) but use real DB.
- **Unit Tests (`tests/unit`)**: **Gap Filling.**
  - Focus on complex domain logic and edge cases that are hard to reach via integration (e.g., specific error handling branches).

### Database Fixtures
- **Default**: Use `async_session_db` fixture.
  - **Why**: Faster. Wraps test in a transaction and rolls back at the end. No data persists.
- **Exception**: Use `async_session_trans` fixture ONLY for testing explicit transaction logic (commits/rollbacks inside application code).
  - **Why**: Slower. Commits data and cleans up via TRUNCATE.

### Assertion Standards
- **Loop Assertions**:
  - **Avoid**: Try to avoid loops for assertions if `assert list == expected_list` works.
  - **Identified**: If you MUST loop, include an identifier in the assert message so failures are debuggable.
    - **Bad**: `for item in items: assert item.active`
    - **Good**: `for i, item in enumerate(items): assert item.active, f"Item {i} (id={item.id}) failed"`

### Fixtures & Factories
- **Technology**: `polyfactory`.
  - Use `DataclassFactory` for Entities.
  - Use `ModelFactory` for Pydantic Schemas/Models.
  - Use `SQLAlchemyFactory` for SQLAlchemy Models.
- **DB Interaction in Tests**:
  - Use `async_engine.connect()` for DB admin tasks (DROP/CREATE).
  - Use `async_engine.begin()` for Schema operations (Create Tables).
