# New Music Provider Scaffold

You are scaffolding a new music provider integration for MuseFlow.

Provider name: **$ARGUMENTS**

Use the Spotify integration (`museflow/infrastructure/adapters/providers/spotify/`) as the reference implementation. Mirror its structure exactly unless there is a clear reason not to.

## Files to create

### Settings
`museflow/infrastructure/config/settings/<name>.py`
```python
class <Name>Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="<NAME>_", ...)
    API_KEY: str
    BASE_URL: HttpUrl = Field(default=HttpUrl("https://api.<name>.com/..."))
    HTTP_TIMEOUT: float = 30.0
    HTTP_MAX_RETRIES: int = 5
```

### Provider package — `museflow/infrastructure/adapters/providers/<name>/`

| File | Purpose |
|------|---------|
| `__init__.py` | Empty |
| `exceptions.py` | Provider-specific exceptions (e.g., `<Name>TokenExpiredError`) |
| `types.py` | Enums: scopes, content types |
| `schemas.py` | Pydantic DTOs matching the external API shape exactly |
| `mappers.py` | Standalone `to_domain_*(dto)` functions |
| `client.py` | Async HTTP client with tenacity retry logic (mirror Spotify client) |
| `session.py` | OAuth session wrapper (if applicable) |
| `library.py` | Implements `ProviderLibraryPort` — fetch tracks, artists, etc. |

### Retry logic in `client.py`
Follow the Spotify pattern:
- `_is_retryable_error(exception)` — return `False` for token errors and `ProviderRateLimitExceeded`
- `@retry(retry=retry_if_exception(_is_retryable_error), wait=wait_exponential(...), stop=stop_after_attempt(...))`
- Handle 429 with `Retry-After` header: check against `max_retry_wait`, raise `ProviderRateLimitExceeded` if exceeded, otherwise `asyncio.sleep()` + `TryAgain()`

### Domain exceptions (if new ones are needed)
Add to `museflow/domain/exceptions.py` — e.g., provider-agnostic `ProviderRateLimitExceeded` is already there.

### Port (if new capabilities are needed)
Add to `museflow/application/ports/providers/` if the new provider introduces capabilities beyond existing ports.

### Wire up in dependencies
- `museflow/infrastructure/entrypoints/api/dependencies.py`
- `museflow/infrastructure/entrypoints/cli/dependencies.py`

## WireMock stubs
Create stub response files in `tests/assets/wiremock/<name>/` for:
- Successful API responses (tracks, artists, library)
- 429 Too Many Requests (with and without `Retry-After`)
- 401 Unauthorized
- 5xx Server Error

## Tests to create

### Unit tests — `tests/unit/infrastructure/adapters/providers/<name>/`
- `test_client.py` — retry logic, 429 handling, token expiry, network errors, max retry wait
- `test_mappers.py` — DTO to domain entity mapping
- `test_library.py` (if applicable)

### Integration tests — `tests/integration/infrastructure/providers/<name>/`
- `test_client.py` — happy path against WireMock
- `test_library.py` — full library sync flow

### Factories
- `tests/unit/factories/` — any new domain entities introduced by this provider

## Conventions reminders
- All DTOs live in `schemas.py` and match the API shape exactly (no domain logic)
- All transformation logic lives in `mappers.py` as standalone functions
- `JSONB`/`ARRAY` from `sqlalchemy.dialects.postgresql` if new DB models are needed
- `ProviderRateLimitExceeded` is a domain exception — raise it from the client, not in mappers
- After scaffolding, run `make lint` and `make test`
