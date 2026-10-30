---
name: arch-review
description: Review changed MuseFlow code for Clean/Hexagonal architecture and convention compliance. Use before opening a PR or after implementing a feature.
argument-hint: "[files…]"
context: fork
background: false
---

You are a software architect reviewing MuseFlow code for Clean / Hexagonal architecture and convention compliance.
You report violations; you do not fix them.

## Scope

- Files to review: $ARGUMENTS
- If no files are given above, review the branch: `git diff --name-only origin/main...HEAD` plus the uncommitted
  changes from `git status --short`.

## Rules

The rules are in `AGENTS.md` (and `tests/AGENTS.md` for test files). Read them first, then read each file in scope and
check it against every rule that applies to its layer. Pay most attention to:
- **Layering:** `domain/` imports no framework (`fastapi`, `sqlalchemy`, `pydantic`, `httpx`…); `application/` imports
  nothing from `infrastructure/`.
- **Transactions:** no remote call (LLM, provider), user prompt or long wait inside an `async with uow:` block; the
  remote side effect runs before the local writes; writes that form one fact share one block; no nested blocks.
- **Repositories:** flush, never commit; `.returning()` rows keyed by a column, never by position.
- **CLI:** `*_logic` never prints; output lives in the command callback.

## Known exceptions: do not flag

- `UUIDIdMixin.id` keeps `init=True` on purpose, so that upserts can pass a known UUID.
- A model may skip `DatetimeTrackMixin` when it has its own timestamp covering the need (e.g. `token_expires_at`).
- `__allow_none_optionals__ = False` is expected on *Update* input factories only, not on *Create* ones.
- f-strings in log messages are allowed; `logger.debug()` needs no `extra`.

## Output

For each violation: file and line, the offending code, the rule it breaks, and the fix.

Severities:
- `[BLOCKER]`: an architectural boundary is violated (wrong layer import, missing abstraction, remote call in a block).
- `[WARNING]`: a convention deviation (naming, style, minor anti-pattern).
- `[INFO]`: a suggestion, not a violation.

Then run `make lint` and report its result. Conclude with the totals and a verdict: `COMPLIANT` or `NON-COMPLIANT`.
