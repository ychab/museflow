# MuseFlow Coding Conventions & Architecture

## 1. Architecture Overview
This project follows **Clean Architecture (Hexagonal)** principles.
- **Domain (`museflow/domain`)**:
  - **Entities**: Pure Python Dataclasses. Represent the "Truth" of the system.
  - **Schemas**: Pydantic Models. Represent "Input/Output" contracts (DTOs/Commands).
  - **Ports**: Interfaces (`abc.ABC`).
  - **Exceptions**: Domain-specific errors.
- **Application (`museflow/application`)**: Orchestrates business logic. Depends ONLY on Domain.
- **Infrastructure (`museflow/infrastructure`)**: Implements details (SQLAlchemy, FastAPI).

## 2. Coding Rules by Layer

### Domain Layer

#### A. Entities (`museflow/domain/entities/`)
- **Technology**: Standard Python `@dataclass(frozen=True, kw_only=True)`.
  - **Immutable**: Entities should not change after creation (use `frozen=True`).
  - **Validation**:
    - **Business Rules ONLY**: Use `__post_init__` to enforce logical consistency (e.g., `start_date < end_date`).
    - **No Tech Constraints**: Do NOT enforce DB limits (e.g., `varchar(255)`) here.
  - **Computed Properties**: Use standard `@property`.
- **Inheritance**: Inherit from `BaseEntity` (provides `id: UUID`, `created_at`, `updated_at`).

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
- **Database (SQLAlchemy 2.0)**:
  - **Models**: Separate SQLAlchemy models.
  - **Queries**: Use `stmt = select(Model).where(...)` pattern.
  - **Writes**: Explicit `session.add()`, `session.commit()`, `session.refresh()`.
  - **Mapping**: Explicitly map `DB Model -> Domain Entity` in the Repository implementation.
- **API (FastAPI)**:
  - **DTOs**: Separate Pydantic models for Requests/Responses if they differ from Domain Schemas.
  - **Injection**: Use `fastapi.Depends` to inject Adapters.
  - **Errors**: Catch Domain Exceptions -> Raise `fastapi.HTTPException`.

## 3. General Python Standards
- **Python Version**: Target **Python 3.13**.
- **Formatting & Linting**:
  - Follow **Ruff** configuration (`pyproject.toml`).
  - **Line Length**: 119 characters.
  - **Imports**: Sorted via `isort`. Grouping: Future > StdLib > FastAPI > Pydantic > SQLAlchemy > ThirdParty > FirstParty (MuseFlow).
- **Typing**:
  - **Strict Type Hints** for ALL arguments and return values.
  - Use native union syntax: `str | None` (NOT `Optional[str]`).
  - Use `uuid.UUID` for IDs.
- **Naming Conventions**:
  - `user` = Domain Entity (Dataclass)
  - `user_db` = SQLAlchemy Model
  - `user_in` = Input Schema (Pydantic)
  - SQL Statements: `stmt`
  - DB Results: `result`

## 4. Testing Strategy

### Philosophy
- **Integration Tests (`tests/integration`)**: **Primary Focus.**
  - Test full flows (DB + API).
  - Use real DB (via `create_test_database` fixture) and `AsyncSession`.
  - Mock external APIs (e.g., Spotify) but NOT the database.
- **Unit Tests (`tests/unit`)**: **Gap Filling.**
  - Focus on complex domain logic (`__post_init__` rules) and edge cases.
  - Extensive mocking allowed.

### Fixtures & Setup
- **Scope**: Use `conftest.py` hierarchies (`tests/`, `tests/integration/`, `tests/unit/`).
- **Data Creation**:
  - **Always use fixtures**.
  - **Factories**: Use `polyfactory` for generating both Dataclasses (Entities) and Pydantic Models (Schemas).
  - **Configurable**: Allow overriding fixture attributes via `request.param`.
- **Combination**: Build fixtures on top of others (e.g., `auth_token` depends on `user`).

#### Example: Configurable Async Fixture
```python
@pytest.fixture
async def user(request) -> User:
    # Allows @pytest.mark.parametrize("user", [{"email": "..."}], indirect=True)
    params = getattr(request, "param", {})
    # Note: Use Entity Factory here, not DB Model Factory directly if possible,
    # or Create DB Model -> Convert to Entity
    user_db = await UserModelFactory.create_async(**params)
    return User(id=user_db.id, email=user_db.email, ...) # Manual map or helper
