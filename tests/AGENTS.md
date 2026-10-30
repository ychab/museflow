# Testing guidelines

Tests are the **contract with our users**: clean, clear and easy to maintain, not just 100% coverage.

## Philosophy
- **100% branch coverage** is mandatory.
- **Integration tests** are the primary focus: full flows with a real DB and WireMock.
- **Unit tests** fill gaps: error branches and edge cases hard to reach via integration.
- **Do not mirror happy paths**: if integration covers the nominal flow, no unit test for the same.
- **Error paths belong in unit tests**, with `AsyncMock` repositories. No fake (in-memory) repositories.
- **All test code is typed**: fixtures, functions, factories, helpers.
- **No inner imports** in test functions: all imports at module level.
- If an assertion must loop, put an identifier in its message:
  `assert item.active, f"Item {i} (id={item.id}) failed"`.

## File mirror
One test file per source file, never consolidated:
```
museflow/application/use_cases/user_create.py
→ tests/unit/application/use_cases/test_user_create.py
→ tests/integration/application/use_cases/test_user_create.py
```

## Fixtures
- Place a fixture as close to its use as possible: class, then module, then `conftest.py`.
- `scope="session"` for expensive shared setup (DB engine, test DB, logging); `scope="function"` (default) for
  anything that touches state. `autouse=True` only when every test in scope needs it.
- `request.param` for parametrized fixtures, never module-level `_make_*` helpers.
- `async_session_db` (rolled back at the end) by default; `async_session_trans` (real commits, TRUNCATE cleanup) only
  to test commit behaviour.
- Use cases get `uow` (integration: each block runs in a savepoint of the test transaction) or `mock_uow` (unit: its
  repositories are the `mock_*_repository` fixtures; `mock_uow.block_open` tells whether a remote call ran inside a
  block).
- **Never `with mock.patch(...)` inside a test**: always a `pytest.fixture`.

## CLI commands
Each command has 3 unit classes (`TestXParserCommand`, `TestXCommand`, `TestXLogic`) and 1 integration `TestXLogic`
(happy path only). Canonical: `tests/unit/infrastructure/entrypoints/cli/commands/users/test_update.py`.

## Factories
- `DataclassFactory` → domain entities, `TypedDictFactory` → TypedDicts, `ModelFactory` → Pydantic,
  `SQLAlchemyFactory` → DB models.
- Never module-level helpers (`_make_*`, `_build_*`): call the factory directly or use a fixture.

## Markers
- `@pytest.mark.slow`: skipped by default, run with `--slow`.
- `@pytest.mark.spotify_live`: requires `--spotify-refresh-token`, hits real Spotify.
- `@pytest.mark.wiremock`: required on any integration class using WireMock (prevents xdist flakiness).

## Dead End Protocol
After 3 failed fix attempts on the same problem, stop and report structured options A/B/C. Full template in the
`test` agent (`.claude/agents/test.md`).
