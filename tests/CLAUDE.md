# Tests

Testing conventions live in two places:
- **Main CLAUDE.md** (`../CLAUDE.md`) — philosophy, file mirror, fixture rules, CLI pattern, factories, markers
- **`test` agent** (`.claude/agents/test.md`) — full process, examples, Dead End Protocol template

Use `/add-tests <file>` to generate tests for a source file, or the `test` agent when `make test` fails.
