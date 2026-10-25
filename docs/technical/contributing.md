# Contributing

MuseFlow is a personal project and showcase, but it is set up so that a change can be made, checked and reviewed the same way each time. This page is the short version; the rules themselves live in [`CONVENTIONS.md`](https://github.com/ychab/museflow/blob/main/CONVENTIONS.md) (detailed reference) and [`CLAUDE.md`](https://github.com/ychab/museflow/blob/main/CLAUDE.md) (the compact contract).

## Setup

Requirements and step-by-step installation (Python 3.14, `uv`, Docker Compose, `direnv`, a Spotify developer app and a Gemini API key) are in the [README](https://github.com/ychab/museflow#readme). In short:

```bash
make install        # dependencies and pre-commit hooks
cp .env.example .env   # then fill in the secrets
make up-db          # PostgreSQL
make db-upgrade     # apply the schema
```

## Make targets

| Target | What it does |
|---|---|
| `make install` | Install dependencies and the pre-commit hooks |
| `make lint` | Ruff check and format, mypy, deptry (mutating: applies fixes) |
| `make lint-check` | The same checks without modifying files; what CI runs |
| `make test` | The full suite with the 100% branch gate (starts PostgreSQL and both WireMock containers, stops them afterwards) |
| `make test-unit` | Unit tests only; needs no containers |
| `make test-integration` | Integration tests (real PostgreSQL, WireMock) |
| `make up`, `make up-db`, `make up-wiremock`, `make down` | Docker Compose services |
| `make db-revision` | Create an Alembic migration |
| `make db-upgrade` / `make db-downgrade` | Apply or roll back migrations |
| `make docs-serve` | Serve this documentation locally with live reload |
| `make docs-build` | Build the documentation in strict mode, as CI does |
| `make run` | Start the FastAPI dev server |

Run `make help` for the full list.

## Branches and commits

- Work on a short-lived branch off `main`, named `<type>/<topic>` (for example `docs/overhaul`).
- Commits follow [Conventional Commits](https://www.conventionalcommits.org/): `feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `chore:`, with an optional scope (`feat(gemini): add self-healing for invalid structured responses`). The convention has been used since the V2 line started in May 2026; earlier history uses free-form messages.
- Everything written for the repository is **in English**: code, comments, docstrings, log messages, CLI help, tests, commit messages and docs.
- Commits made with an AI assistant carry a `Co-Authored-By` trailer.
- Dependency updates arrive as a single weekly Dependabot PR; patch and minor updates are auto-merged, major ones are reviewed by hand (see [Quality & testing](quality.md#continuous-integration)).

## Pull request checklist

- [ ] `make lint-check` passes: Ruff, mypy and deptry are clean.
- [ ] `make test` passes with **100% branch coverage**; every new branch is covered, error paths by unit tests with `AsyncMock`, flows by integration tests.
- [ ] New code follows the layering rule: nothing in `domain/` imports a framework; use cases receive ports, never build repositories or clients.
- [ ] One test file per source file, in the mirrored path under `tests/unit` and `tests/integration`; test code is fully typed and uses factories, not helper functions.
- [ ] Schema changes include an Alembic migration (`make db-revision`); the migration is reviewed for nullable defaults and `downgrade()`.
- [ ] Logs carry no secrets; user-facing output stays in the CLI callback, not in the `*_logic` function.
- [ ] An architecture review has been run (`/arch-review` or the `arch` agent), and a security review (`/security-review` or the `security` agent) when auth, endpoints or external adapters changed.
- [ ] User-visible behaviour changes update the [user guide](../user-guide/index.md); structural changes update these technical pages.

## Working with Claude Code

The repository is configured for [Claude Code](https://claude.ai/claude-code). Rather than re-explaining the rules, use the project's commands and agents:

| Need | Use |
|---|---|
| Scaffold a feature through every layer | `/new-feature <name>` |
| Add a migration | `/new-migration <description>` |
| Write tests for a file | `/add-tests <path>` |
| Add another music provider | `/new-provider <name>` |
| Review a diff before opening a PR | `/arch-review`, `/security-review`, or the `arch` and `security` agents |
| Fix lint, type or dependency errors | the `python` agent |
| Fix failing tests or coverage gaps | the `test` agent (stops after 3 failed attempts and reports options A / B / C) |
| Understand how a flow is wired | the `engineer` agent |

The human contributor stays responsible for every change: review the diff, run the checks, and decide. The full story and the reasoning are in [AI-assisted development](ai-assisted-development.md).

## Notes for tests that touch external APIs

Never add a test that calls the live Gemini or Spotify APIs to the default suite. Live tests are marked `gemini_live` / `spotify_live`, are skipped unless opted in, and cost money or use a real account. Use WireMock stubs under `tests/assets/wiremock/` and mark the class `@pytest.mark.wiremock("spotify")` or `("gemini")` so parallel workers do not race on stubs.
