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
- A failing test is fixed in the test, never by bending the source; if the source is wrong, fix it on purpose.
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
- `mock.AsyncMock` for async ports, `mock.Mock` for sync ones.
- Assert logs with `caplog` (e.g. `with caplog.at_level(logging.ERROR), pytest.raises(SomeError):`), never by patching
  the module `logger`.

## CLI commands
Each command has 3 unit classes (`TestXParserCommand`, `TestXCommand`, `TestXLogic`) and 1 integration `TestXLogic`
(happy path only). Canonical: `tests/unit/infrastructure/entrypoints/cli/commands/users/test_update.py`.
- `TestXParserCommand`: Typer parsing only; `TestXCommand`: the callback (output, try/except), with `*_logic` mocked;
  `TestXLogic`: the logic branches, with a `TARGET_PATH` class attribute pointing to the command module.
- Error paths (user not found, …) belong in the unit `TestXLogic`, not in the integration one.

## Factories
- `DataclassFactory` → domain entities, `TypedDictFactory` → TypedDicts, `ModelFactory` → Pydantic,
  `SQLAlchemyFactory` → DB models.
- Never module-level helpers (`_make_*`, `_build_*`): call the factory directly or use a fixture. A missing factory
  is added to `tests/unit/factories/`.
- `__set_relationships__ = False` on SQLAlchemy factories; `__use_defaults__ = True` on `DataclassFactory` subclasses
  (entity defaults such as `fingerprint = ""` are kept); `__set_as_default_factory_for_type__ = True` on
  `TypedDictFactory` subclasses, chained with `Use(ChildFactory.build)`; `__allow_none_optionals__ = False` on *Update*
  input factories.
- Don't override what polyfactory generates (UUIDs, fields with defaults); set only realistic values (names, emails)
  or values the test depends on.

## Markers
- `@pytest.mark.slow`: skipped by default, run with `--slow`.
- `@pytest.mark.spotify_live`: requires `--spotify-refresh-token`, hits real Spotify.
- `@pytest.mark.wiremock`: required on any integration class using WireMock (prevents xdist flakiness).

## Dead End Protocol
After 3 failed fix attempts on the same problem, stop and report structured options A/B/C. Full template in the
`test` agent (`.claude/agents/test.md`).
