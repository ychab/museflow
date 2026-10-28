# Quality & testing

## Philosophy

The testing rules are written in [`CLAUDE.md`](https://github.com/ychab/museflow/blob/main/CLAUDE.md) and [`CONVENTIONS.md`](https://github.com/ychab/museflow/blob/main/CONVENTIONS.md) and are meant to read as a contract: tests describe what the system promises, not how it is wired.

| Principle | In practice |
|---|---|
| **Integration tests are the primary focus** | Full flows run against a real PostgreSQL and WireMock stand-ins for Spotify and Gemini, so SQL (including the `ON CONFLICT` merge rules), HTTP mapping and use-case orchestration are exercised together |
| **Unit tests fill gaps** | Error branches and edge cases that are awkward to reach end to end: rate-limit exhaustion, invalid LLM replies, empty inputs. Ports are replaced with `mock.AsyncMock` / `mock.Mock(spec=Port)` |
| **No fake in-memory repositories** | A fake repository is a second implementation that can disagree with the real one. The real one runs against a real database; the mock only asserts calls |
| **Do not mirror happy paths** | If an integration test covers the nominal flow, there is no unit test repeating it |
| **100% branch coverage, mandatory** | `fail_under = 100` with `branch = true`; coverage `source` includes `tests/` itself, so dead test code fails the gate too |
| **One test file per source file** | `museflow/application/use_cases/user_create.py` maps to `tests/unit/.../test_user_create.py` and `tests/integration/.../test_user_create.py`. Never consolidated, so the location of a test is predictable |
| **Typed test code** | Fixtures, factories and helpers carry full type hints, and mypy checks `tests/` as well |
| **Fixtures as close to use as possible** | Class, then module, then `conftest.py`; no `with mock.patch(...)` inside a test body, a fixture instead |
| **Factories, not helpers** | `polyfactory` factories (`DataclassFactory` for entities, `ModelFactory` for Pydantic, `SQLAlchemyFactory` for DB models, `TypedDictFactory` for TypedDicts). Module-level `_make_*` builders are banned |

Honest reading of the numbers: by count, unit tests outnumber integration tests (721 to 279 test functions). "Integration-first" describes where flows are proven and where effort goes, not the ratio of functions; the unit tests are many because every CLI command carries three small unit classes (parser, command, logic) beside one integration test of the logic.

## Numbers

Measured on the current tree:

| Metric | Value |
|---|---|
| Test functions (`def test_`) | 1,000 (parametrisation expands this at run time) |
| Test files | 146 (77 unit, 69 integration) |
| Unit / integration functions | 721 / 279 |
| Source lines (`museflow/`) | ~12,100 |
| Test lines (`tests/`) | ~21,300 |
| Coverage gate | 100% branch |

## Test infrastructure

**Real database, isolated per worker.** The integration suite creates a dedicated database at session start and drops it at the end. Under `pytest-xdist` each worker gets its own (`test_<name>_<worker_id>`), so parallel runs never share rows. The schema is created from the SQLAlchemy metadata (`Base.metadata.create_all`), not by replaying Alembic migrations, so migrations are not exercised by the suite.

**Two session fixtures.** `async_session_db` is the autouse default: the test runs inside an outer transaction that is rolled back at the end, which is fast and needs no cleanup. The code under test writes through its unit of work, whose blocks run on the same connection with `join_transaction_mode="create_savepoint"`: each block's commit releases a savepoint, so the test sees the rows and they still disappear at the end. Since those writes go through other sessions, the test session reloads rows on every SELECT (`populate_existing`) instead of serving what it cached. `async_session_trans` is for the rare test where real commit semantics matter (the unit of work itself); it commits for real and cleans up with `TRUNCATE ... RESTART IDENTITY CASCADE`, which is slower.

**WireMock for both external APIs.** `docker-compose.yml` starts one WireMock container for Spotify and one for Gemini, with stub assets under `tests/assets/wiremock/`. A small `WireMockContext` creates per-test mappings and deletes them on exit, and resets scenario state when scenarios were used. Adapter tests therefore exercise real HTTP, retries and header handling.

**Parallelism without WireMock races.** WireMock is a shared mutable resource: a one-off stub created by one test can match a request from another test running on a different worker. Tests that use it are marked `@pytest.mark.wiremock("spotify")` or `("gemini")` (or both). A collection hook in [`tests/conftest.py`](https://github.com/ychab/museflow/blob/main/tests/conftest.py) groups tests by server using union-find: if any test uses both servers, the two servers merge into one group transitively. Each group becomes one `xdist_group`, which `--dist=loadgroup` pins to a single worker so its tests run serially. The rest of the suite still runs fully parallel (`-n auto`). The history of this fix (a per-ID cleanup first, then the union-find grouping) is in the git log; the mechanism is documented in the hook's docstring.

**Markers for what must not run by default.**

| Marker | Behaviour |
|---|---|
| `spotify_live` | Hits the real Spotify API; skipped unless `--spotify-refresh-token` is passed |
| `gemini_live` | Hits the real Gemini API; skipped unless `--gemini-live` is passed. Spends real money |
| `slow` | Skipped unless `--slow` is passed (registered; no test currently uses it) |
| `wiremock(*servers)` | Grouping marker described above |

The live tests are a deliberate manual step, never part of `make test` or CI.

**Time.** `time-machine` freezes the clock through a `frozen_time` fixture where timestamps matter.

## Static analysis

| Tool | Role | Configuration |
|---|---|---|
| Ruff | Lint and format, line length 119 | Rule sets `E F I UP B PERF FURB` plus `S101` (no `assert` outside tests); isort with one import per line and custom sections (FastAPI, Pydantic, SQLAlchemy grouped separately) |
| mypy | Static typing over `museflow` and `tests` | `strict = true`, Pydantic plugin on, Python 3.14 target |
| deptry | Unused, missing and transitive dependency detection | `asyncpg` allow-listed as a driver loaded by SQLAlchemy |
| pre-commit | Runs the above plus hygiene hooks (merge-conflict markers, YAML / TOML / JSON validity, trailing whitespace, debug statements) | `.pre-commit-config.yaml` |

`make lint` formats and checks locally; `make lint-check` is the non-mutating variant used in CI.

## Continuous integration

| Workflow | Trigger | What it does |
|---|---|---|
| [`ci.yml`](https://github.com/ychab/museflow/blob/main/.github/workflows/ci.yml) | Push to and pull requests on `main` | Install `uv` (version pinned) and Python 3.14, `make install-deps`, `make lint-check`, `make test` (starts PostgreSQL and both WireMock containers, runs the suite with the 100% gate), upload `coverage.xml` and `junit.xml` to Codecov |
| [`docs.yml`](https://github.com/ychab/museflow/blob/main/.github/workflows/docs.yml) | Changes under `docs/`, `zensical.toml` or dependency files | Builds this site with `make docs-build` (strict, so broken links and references fail the build); on `main`, deploys to GitHub Pages |
| [`dependabot-auto-merge.yml`](https://github.com/ychab/museflow/blob/main/.github/workflows/dependabot-auto-merge.yml) | Pull requests from Dependabot | Enables auto-merge for patch and minor updates; major bumps stay manual |

[`dependabot.yml`](https://github.com/ychab/museflow/blob/main/.github/dependabot.yml) updates Python dependencies (`uv`, grouped into one weekly PR), GitHub Actions, Dockerfile base images and Compose service images. `pydantic-core` is ignored because it is version-locked to Pydantic. Auto-merge only waits for CI if the repository's branch protection requires it; that setting is not visible from the code.

A recurring maintenance cost is visible in the history: dependency bumps regularly require code adaptations (for example commit `fix: adapt codebase to bumped dependencies`), which is the price of a 100% gate on fast-moving libraries and also what makes the bumps safe to merge.
