# MuseFlow Project Guidelines

## Core Stack & Tools
* **Python:** 3.13 managed by `uv`.
* **Frameworks:** FastAPI, Typer (CLI), SQLAlchemy 2.0 (async).
* **Validation/Mapping:** Pydantic v2.

## Architecture Rules (Strict Clean Architecture)
* **Domain (`museflow/domain`):** Must use standard Python `@dataclass(frozen=True, kw_only=True)` for entities. NO framework dependencies here. Enforce business rules in `__post_init__`. Use `abc.ABC` for Ports.
* **Application (`museflow/application`):** Use cases are standalone `async def` functions (or classes with `__call__`). They orchestrate logic and depend ONLY on the Domain. Never instantiate repositories here; use dependency injection.
* **Infrastructure (`museflow/infrastructure`):** SQLAlchemy models use `MappedAsDataclass` + `Base`. Implement `to_entity(self)` to map to domain models.

## Coding Style & Types
* Target 100% strict type hinting (`str | None`, `uuid.UUID`).
* Naming conventions: `user` (Domain), `user_db` (SQLAlchemy), `user_in` (Pydantic), `user_dto` (External API).
* Use `logger = logging.getLogger(__name__)`. Never log secrets; use `extra={"user_id": ...}` for structured context instead of f-strings.

## Testing Standards
* Target: 100% Branch Coverage (`pytest-cov --cov-fail-under=100`).
* Use `polyfactory` for test data generation (`DataclassFactory` for domain, `ModelFactory` for Pydantic, `SQLAlchemyFactory` for DB).
* Use the `async_session_db` fixture by default to roll back state.

## Commands
* Install: `make install`
* Lint/Format: `make lint`
* Test: `make test`
