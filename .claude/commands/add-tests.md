# Add Tests for a Source File

You are generating tests for an existing MuseFlow source file, targeting 100% branch coverage.

File to test: **$ARGUMENTS**

## Process

### 1. Read and analyze the source file
- Read the file at the given path
- Identify every branch: `if/else`, early returns, exception paths, loop bodies, optional chaining
- Note all dependencies (repositories, ports, external services) that will need to be mocked or injected

### 2. Determine test type(s) needed
- **Integration test** (primary): Use the real DB + real implementations. Write these first.
- **Unit test** (gap-filling): Use mocks. Write these for branches hard to reach via integration (e.g., specific error handling, internal helper functions, edge cases).
- **Do NOT** write a unit test for a happy path already covered by an integration test — this is duplication, not coverage. If the integration test covers the nominal flow, unit tests only need to cover unreachable-via-integration branches.
- **Do NOT** create fake (in-memory) repository implementations. Use `AsyncMock` for repository mocks in unit tests.

### 3. Check for existing fixtures and factories
Before creating new fixtures or factories, check:
- `tests/unit/conftest.py` and `tests/integration/conftest.py` — shared fixtures
- `tests/unit/factories/` — entity and input factories
- `tests/integration/factories/models/` — SQLAlchemy model factories
- Reuse existing ones; create new ones only when necessary

### 4. Create factory files (if needed)

**Unit factory — domain entity:**
```python
# tests/unit/factories/entities/<name>.py
class EntityFactory(DataclassFactory[Entity]):
    __model__ = Entity
```

**Unit factory — Pydantic input:**
```python
# tests/unit/factories/inputs/<name>.py
class EntityCreateInputFactory(ModelFactory[EntityCreateInput]):
    __model__ = EntityCreateInput
    __allow_none_optionals__ = False
```

**Integration factory — SQLAlchemy model:**
```python
# tests/integration/factories/models/<name>.py
class EntityModelFactory(BaseModelFactory[EntityModel]):
    __model__ = EntityModel
    __set_relationships__ = False
    field = Use(BaseModelFactory.__faker__.method)
```

### 5. Write the tests

**Test class structure:**
```python
class TestMyThing:
    async def test__nominal(self, ...) -> None: ...
    async def test__<branch_condition>(self, ...) -> None: ...
    async def test__<error_case>(self, ...) -> None: ...
```

**Integration test pattern:**
```python
async def test__nominal(
    self,
    async_session_db: AsyncSession,   # auto-rollback
    user_repository: UserRepository,  # real implementation
    password_hasher: PasswordHasherPort,
) -> None:
    result = await use_case(input, user_repository, password_hasher)
    # Verify via DB query
    stmt = select(Model).where(Model.id == result.id)
    db_row = (await async_session_db.execute(stmt)).scalar_one_or_none()
    assert db_row is not None
```

**Unit test pattern:**
```python
async def test__raises_when_not_found(
    self,
    mock_user_repository: mock.AsyncMock,
) -> None:
    mock_user_repository.get_by_id.return_value = None
    with pytest.raises(UserNotFound):
        await use_case(user_id, mock_user_repository)
```

### 6. Coverage rules
- Every `if` branch needs at least one test for the truthy path and one for the falsy path
- Every `except` block needs a test that triggers it
- Every early `return` needs a test
- Every `for` loop needs: a test with items AND a test with an empty collection (if reachable)

### 7. Typing
All test functions, fixtures, and helpers must have full type annotations. Return type of test functions is `None`.

### 8. Verify
After writing tests, run:
```bash
make test-unit   # or make test-integration
```
If coverage is below 100%, identify the missing branches and add tests.

## Conventions reminders
- Test method naming: `test__<scenario>` or `test__<method>__<scenario>`
- Class naming: `Test<SubjectClass>` or `Test<SubjectFunction>`
- `async_session_db` (auto-rollback) by default; `async_session_trans` only for explicit commit testing
- `mock.AsyncMock` for async ports, `mock.Mock` for sync
- Add new shared fixtures to the appropriate `conftest.py`, not inside the test file
