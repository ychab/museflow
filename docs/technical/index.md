# Technical overview

MuseFlow is a Python backend with a CLI as its primary interface and a small FastAPI surface for the OAuth callback and user endpoints. It is organised as a hexagonal (ports and adapters) application. This section documents how it is built and why, with each claim traceable to code in the [repository](https://github.com/ychab/museflow).

## Stack

| Concern | Choice | Notes |
|---|---|---|
| Language / tooling | Python 3.14, [`uv`](https://docs.astral.sh/uv/) | Dependencies locked in `uv.lock`; `Makefile` wraps every workflow |
| Entrypoints | Typer (CLI), FastAPI (API) | Both are thin: parse, call a use case, render |
| Persistence | PostgreSQL, SQLAlchemy 2 async (`asyncpg`), Alembic | PostgreSQL-specific features on purpose: `JSONB`, `ARRAY`, `ON CONFLICT` upserts |
| Validation | Pydantic v2, `pydantic-settings` | External DTOs, structured LLM output, settings |
| HTTP | `httpx` (async) + `tenacity` | One shared client mixin, per-adapter retry policies |
| LLM | Google Gemini over REST | Several models, one per pipeline step (see [LLM pipeline](llm-pipeline.md)) |
| Matching | `rapidfuzz`, `unidecode` | Fuzzy reconciliation and text normalisation |
| Quality | pytest, polyfactory, WireMock, Ruff, mypy, deptry, pre-commit | See [Quality & testing](quality.md) |

## Size at a glance

Measured on the current `HEAD` of the branch this documentation was written on:

| Metric | Value |
|---|---|
| Source (`museflow/`, Python lines) | ~12,100 |
| Tests (`tests/`, Python lines) | ~21,300 |
| Test functions | 1,000 across 146 test files (721 unit, 279 integration) |
| Coverage gate | 100% branch, enforced by `fail_under = 100` |
| Alembic migrations | 1 (a squashed `initial` migration, edited in place during V2 development, see [Data model](data-model.md)) |

## Where to go next

<div class="grid cards" markdown>

-   **Architecture**

    ---

    Layers, the dependency rule, ports and adapters, and a sequence diagram of `playlist discover` from CLI to Spotify.

    [:octicons-arrow-right-24: Architecture](architecture.md)

-   **Data model**

    ---

    Tables, the fingerprint identity, per-track play aggregation, the genre and mood vocabularies.

    [:octicons-arrow-right-24: Data model](data-model.md)

-   **LLM pipeline**

    ---

    Profiler, advisor, reconciler and enricher; model choice per step; retries and self-healing of structured output.

    [:octicons-arrow-right-24: LLM pipeline](llm-pipeline.md)

-   **Privacy & data**

    ---

    What is stored, what is dropped at import, what leaves the machine, and the known gaps stated plainly.

    [:octicons-arrow-right-24: Privacy & data](privacy-and-data.md)

-   **Quality & testing**

    ---

    Integration-first testing, the 100% branch gate, static analysis and CI.

    [:octicons-arrow-right-24: Quality & testing](quality.md)

-   **AI-assisted development**

    ---

    How conventions, a `CLAUDE.md` contract, commands and reviewer agents were introduced, with dates and commits.

    [:octicons-arrow-right-24: AI-assisted development](ai-assisted-development.md)

-   **Contributing**

    ---

    Make targets, commit conventions and the PR checklist.

    [:octicons-arrow-right-24: Contributing](contributing.md)

</div>
