#!/usr/bin/env bash
# PostToolUse hook: format and lint each Python file Claude edits, and feed the remaining errors back to Claude.
set -euo pipefail

file_path=$(jq -r '.tool_input.file_path // empty')
cd "$CLAUDE_PROJECT_DIR"

case "$file_path" in
    "$CLAUDE_PROJECT_DIR"/museflow/*.py | "$CLAUDE_PROJECT_DIR"/tests/*.py) ;;
    *) exit 0 ;;
esac

uv run --quiet ruff format --quiet "$file_path"

# F401 is ignored: an import added in one edit and used in the next would be removed in between.
# Unused imports are still caught by `make lint` and pre-commit.
if ! errors=$(uv run --quiet ruff check --fix --quiet --extend-ignore F401 "$file_path" 2>&1); then
    echo "$errors" >&2
    exit 2
fi
