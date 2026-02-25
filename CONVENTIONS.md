# MuseFlow Coding Conventions & Architecture

## 1. Architecture Overview
This project follows **Clean Architecture (Hexagonal)** principles.
- **Domain (`museflow/domain`)**: Pure Python/Pydantic. NO external dependencies (no SQL, no HTTP frameworks). Contains Entities, Exceptions, and Ports (Interfaces).
- **Application (`museflow/application`)**: Orchestrates business logic. Contains Use Cases. Depends ONLY on Domain.
- **Infrastructure (`museflow/infrastructure`)**: Implements details. Contains Database Adapters, API Endpoints, and CLI. Depends on Application and Domain.

## 2. Coding Rules by Layer

### Domain Layer
- **Entities**: Use `pydantic.BaseModel` (v2) for coherence.
  - Inherit from `BaseEntity`
  - Use `Field(...)` for validation (length, regex).
  - Use `@model_validator(mode="after")` for complex cross-field validation.
  - **Strictness**: Avoid `Optional`. Use `Type | None = None` instead.
- **Ports**: Define interfaces using **Abstract Base Classes (`abc.ABC`)**.
  - Placed in `museflow/domain/ports/`.
  - Naming: `SomethingPort` or `SomethingRepository`.

### Application Layer (Use Cases)
- **Structure**:
  - **Default**: Standalone **async functions** (e.g., `async def user_create(...) -> User`).
  - **Complex**: Use a **Class** with `__call__` or `execute` method if state/refactoring is needed.
- **Dependency Injection**: Accept Ports as arguments. DO NOT instantiate repositories inside use cases.

### Infrastructure Layer
- **Database (SQLAlchemy 2.0)**:
  - Use `Mapped[...]` and `mapped_column(...)` for strict typing.
  - **Queries**: Use `stmt = select(Model).where(...)` pattern.
  - **Writes**: Explicit `session.add()`, `session.commit()`, and `session.refresh()`.
  - **Updates**: Use `stmt = update(Model).values(**data).returning(Model)`.
- **API (FastAPI)**:
  - **DTOs**: Separate Pydantic models for Requests/Responses.
  - **Injection**: Use `fastapi.Depends` to inject Adapters.
  - **Errors**: Catch Domain Exceptions -> Raise `fastapi.HTTPException`.

## 3. General Python Standards
- **Python Version**: Target **Python 3.13**.
- **Formatting & Linting**:
  - Follow **Ruff** configuration (`pyproject.toml`).
  - **Line Length**: 119 characters.
  - **Imports**: Sorted via `isort` (Ruff). Grouping: Future > StdLib > FastAPI > Pydantic > SQLAlchemy > ThirdParty > FirstParty (MuseFlow).
- **Typing**:
  - **Strict Type Hints** for ALL arguments and return values.
  - Use native union syntax: `str | None` (NOT `Optional[str]`).
  - Use `uuid.UUID` for IDs (not `str`).
- **Naming Conventions**:
  - SQL Statements: `stmt`
  - DB Results: `result`
  - Variable names should be descriptive (e.g., `user_db` vs `user_entity`).
- **Comments**: Minimal. Code must be self-documenting.

---

## 4. Testing Strategy

### Philosophy
- **Integration Tests (`tests/integration`)**: **Primary Focus.**
  - Test full flows (DB + API/CLI).
  - Use real DB (via `create_test_database` fixture) and `AsyncSession`.
  - Mock external APIs (e.g., Spotify) but NOT the database.
- **Unit Tests (`tests/unit`)**: **Gap Filling.**
  - Focus on complex domain logic/edge cases.
  - extensive mocking allowed.

### Fixtures & Setup
- **Scope**: Use `conftest.py` hierarchies (`tests/`, `tests/integration/`, `tests/unit/`).
- **Data Creation**:
  - **Always use fixtures**.
  - **Factories**: Use `polyfactory` to generate models.
  - **Configurable**: Allow overriding fixture attributes via `request.param`.
- **Combination**: Build fixtures on top of others (e.g., `auth_token` depends on `user`).

#### Example: Configurable Async Fixture
```python
@pytest.fixture
async def user(request) -> User:
    # Allows @pytest.mark.parametrize("user", [{"email": "..."}], indirect=True)
    params = getattr(request, "param", {})
    user_db = await UserModelFactory.create_async(**params)
    return User.model_validate(user_db)
```

### Mocking
- **Target**: Use `unittest.mock.patch` to mock dependencies.
- **Fixtures**: Wrap mocks in fixtures for reusability.
- **Class Mocking**: When mocking a class, yield `patched.return_value` from the fixture to directly access the mocked instance in tests.
- **Autospec**: Use `autospec=True` when patching classes to automatically create mocks that respect the class signature (including async methods).

#### Example: Mocking a Use Case Class
```python
@pytest.fixture
def mock_my_use_case() -> Iterable[mock.Mock]:
    target_path = "path.to.MyUseCase"
    # autospec=True ensures that async methods are mocked as AsyncMock
    with mock.patch(target_path, autospec=True) as patched:
        yield patched.return_value

def test_something(mock_my_use_case: mock.Mock):
    # mock_my_use_case is the mocked instance
    # Since execute is async, the mock is automatically an AsyncMock
    mock_my_use_case.execute.return_value = "mocked_result"
    ...
```
