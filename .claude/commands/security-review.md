# Security Review

You are reviewing MuseFlow code for security vulnerabilities.

## What to review

If `$ARGUMENTS` is provided, review only those files. Otherwise, review all files changed since the last commit:
```bash
git diff --name-only HEAD
```

Read each changed file and check for the violations below.

## Checklist

### Secrets & Credentials
- [ ] No hardcoded credentials, API keys, tokens, or passwords anywhere in source code
- [ ] Secrets sourced exclusively from `Pydantic BaseSettings` (env vars) — never from literals
- [ ] No secrets logged (access tokens, refresh tokens, client secrets, passwords)
  - Allowed in logs: `user_id`, `status_code`, `provider`, non-sensitive metadata
- [ ] API responses never expose raw OAuth tokens or hashed passwords beyond what is strictly necessary

### Authentication & Authorization (FastAPI endpoints)
- [ ] Every protected endpoint injects `current_user: User = Depends(get_current_user)` — not just the ones that look sensitive
- [ ] `get_current_user` dependency is the **only** mechanism used for JWT verification — no manual `jwt.decode()` calls in route handlers
- [ ] The `/register` and `/login` endpoints are intentionally public — verify no sensitive data is leaked in error messages (e.g., "user not found" vs "invalid credentials" distinction is preserved to avoid user enumeration)
- [ ] OAuth state tokens are single-use (consumed via `auth_state_repository.consume()`) — never reusable
- [ ] `get_user_from_state` is used for the OAuth callback (not `get_current_user`) — ensure the state is always validated and consumed before processing

### Input Validation
- [ ] All data entering the system at API boundaries goes through Pydantic models (no raw `request.body()` or `dict` parsing)
- [ ] All data entering via CLI goes through Typer with typed parameters and Pydantic input schemas
- [ ] File paths from user input (e.g., `--directory` in the history command) are used with `Path` — verify no `open(str_from_user)` or shell interpolation
- [ ] `batch_size` and similar numeric inputs have explicit `min`/`max` constraints in Typer options

### SQL Safety
- [ ] No raw SQL strings with user-supplied values (f-strings, `.format()`, `%` substitution into queries)
- [ ] All DB queries use SQLAlchemy ORM constructs or `text()` with `bindparam()` — never string concatenation

### External API Calls
- [ ] `httpx` client is always used with a timeout (check `SpotifyOAuthClientAdapter` and any new clients)
- [ ] SSL verification is NOT disabled (`verify=False` is forbidden)
- [ ] `Retry-After` values from 429 responses are checked against `max_retry_wait` before sleeping — never sleep an unbounded duration
- [ ] `ProviderRateLimitExceeded` is raised (not silently swallowed) when `Retry-After` exceeds the max

### Error Handling & Information Leakage
- [ ] Generic `Exception` catch blocks in CLI commands use `str(e)` only for user-facing messages — not full tracebacks (those go to the logger)
- [ ] HTTP error responses never include internal stack traces or raw exception messages that reveal implementation details
- [ ] `logger.exception()` (with traceback) used inside `except` blocks for ERROR-level logging — never `logger.error(str(e))`

### Dependency Audit
Run:
```bash
uv audit
```
- [ ] No known CVEs in direct or transitive dependencies
- [ ] If vulnerabilities are found, note the severity and whether they affect code paths used in this project

## Output format

For each violation found:
1. State the file and line number
2. Quote the offending code
3. Explain the security risk
4. Suggest the correct fix

If no violations are found, confirm the code is secure.

After the review, run `make lint` to catch any additional type or style issues.
