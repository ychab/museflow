# Testing guidelines

Tests are the **contract with our users**: clean, clear and easy to maintain, not just 100% coverage.

## Philosophy
- **100% branch coverage** is mandatory.
- **Integration tests** are the primary focus: full flows with a real DB and WireMock.
- **Unit tests** fill gaps: error branches and edge cases hard to reach via integration.
- **Do not mirror happy paths**: if integration covers the nominal flow, no unit test for the same.
- **Coverage is measured on the whole suite**: no dedicated test for a line another test already runs, nor to check a
  third-party library's behaviour.
- **Error paths** go where the error comes from:
  - an error our code decides (user not found → raise) belongs in a unit test, with `AsyncMock` repositories, even
    when an integration test also runs through it;
  - an error produced by the database or an external API (constraint violation, WireMock 4xx) belongs in an
    integration test: a mock would only assert our assumption about it.
  No fake (in-memory) repositories.
- **A unit test whose coverage an integration test contains is a mirror**: remove it. If it asserts something the
  integration test doesn't (an argument passed, a batch size), move the assertion into the integration test, on the
  observable outcome, first. Measure with `--cov-context=test` (issue #92).
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

## Naming
- **Classes:** `Test<Subject>`, named after what they test (`TestTrack`, `TestCreateUserUseCase`); CLI commands follow
  [CLI commands](#cli-commands).
- **Tests:** `test__<part>__<part>`: parts separated by a double underscore, from the general to the specific (method
  or field, then condition, then outcome), words within a part by a single underscore:
  `test__update_email__already_exists`, `test__make_api_call__retry__rate_limit__without_header`.
- `test__nominal` for the happy path; when a class covers several methods, `test__<method>__nominal`.

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
- A fixture is named after what it does to the patched callable: `mock_<name>` replaces it, `spy_<name>` wraps it
  (`wraps=`) so the real code still runs and the call is recorded.
- Mocks and spies belong in unit tests. An integration test asserts the observable outcome (result, rows, requests
  received by WireMock); when a value only shows as an argument passed, test its source where it is produced (e.g. the
  repository) and the forwarding in a unit test. Exceptions, mocked in integration too:
  - what an integration test can't run: terminal input (`typer.prompt`), a real device (`play_track`), the logging
    setup;
  - the use case called by a CLI command's integration `TestXLogic`: that test checks the real wiring (user and token
    loaded from the database), and relies on the use case's own integration tests for the rest.
- Assert logs with `caplog` (e.g. `with caplog.at_level(logging.ERROR), pytest.raises(SomeError):`), never by patching
  the module `logger`.

## CLI commands
Each command has 3 unit classes (`TestXParserCommand`, `TestXCommand`, `TestXLogic`) and 1 integration `TestXLogic`
(happy path only). Canonical: `tests/unit/infrastructure/entrypoints/cli/commands/users/test_update.py`.
- `X` is `<Group><Command>`, like the production names: `TestPlaylistHistoryLogic` tests `playlist_history_logic`
  (`museflow playlist history`), patched by the fixture `mock_playlist_history_logic`.
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
- Never bound a field to fit its column: `SQLAlchemyFactory` already reads the column limits (`String` length,
  `Numeric` precision). A `DataclassFactory` knows no column: bound only a field whose generated value breaks a save
  (an unbounded `Decimal`), with a comment saying why.

## Markers
- `@pytest.mark.slow`: skipped by default, run with `--slow`.
- `@pytest.mark.spotify_live`: requires `--spotify-refresh-token`, hits real Spotify.
- `@pytest.mark.wiremock`: required on any integration class using WireMock (prevents xdist flakiness).

## Dead End Protocol
After 3 failed fix attempts on the same problem, stop and report structured options A/B/C. Full template in the
`test` agent (`.claude/agents/test.md`).
