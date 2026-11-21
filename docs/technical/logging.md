# Logging and output

A command talks to two readers: the person at the terminal, who wants a result and to follow a long run, and the
developer or the log aggregator, who wants to know what happened and why. MuseFlow keeps them apart: one stream each,
one option each, and one handler per kind of reader.

## Two streams

| Stream | Carries | Why |
|---|---|---|
| **stdout** | The results only: the tables, the playlist created, the profile, the JSON of `taste view`, the LLM cost line | A result can be piped or redirected (`museflow taste view --name main > profile.json`) |
| **stderr** | The logs, the progress display, the warnings and errors | Diagnostics never end up in a redirected result |

The logging handlers and the progress display share one Rich console on stderr (`console_stderr` in
`infrastructure/config/loggers/setup.py`): a log line prints above the live progress line instead of breaking it.

## Handlers

Chosen with `--log-handlers` on the CLI (repeatable) or the settings `MUSEFLOW_LOG_HANDLERS_CLI`,
`MUSEFLOW_LOG_HANDLERS_API` and `MUSEFLOW_LOG_HANDLERS_WORKER`:

| Handler | Output | For |
|---|---|---|
| `console` (default) | Plain text with the time, level and code location: `[2026-11-16 15:40:53] DEBUG [museflow.application.services.discovery.get_unknown_artist_tracks:101] Artist tracks: 12 found, …` | Servers and CI logs: the location points at the code |
| `rich` | Colours and the time, no location; enables the animated progress line (spinner, bar, time left) | The terminal |
| `json` | One JSON object per line, `extra` included (see below); the progress display is silenced | A log aggregator (API and workers in production, CLI run by cron) |
| `null` | Nothing | Tests |

The levels come from `--log-level` / `-l` (CLI) and the settings `MUSEFLOW_LOG_LEVEL_CLI`, `MUSEFLOW_LOG_LEVEL_API`,
`MUSEFLOW_LOG_LEVEL_WORKER` (`INFO` by default: a job's progress goes there) for the `museflow` loggers, `MUSEFLOW_LOG_LEVEL_THIRD_PARTY` for the libraries. Two libraries stay at `WARNING`
whatever the setting: from `INFO`, `sqlalchemy.engine` logs the SQL with its parameters (tokens, password hashes) and
`httpx` every URL with its query string. The uvicorn access logs, one line per request, follow
`MUSEFLOW_LOG_LEVEL_THIRD_PARTY` too: the `museflow-app` container gets it from the shell or `.env`, `INFO` shows them.

### The JSON line

```json
{"timestamp": "2026-11-16T15:40:53.123+00:00", "level": "DEBUG", "logger": "museflow.application.services.discovery", "function": "get_unknown_artist_tracks", "line": 101, "message": "Artist tracks: 12 found, 10 by the artist, 4 unknown (2/3 artists left)", "extra": {"found": 12, "matched": 10, "unknown": 4, "artists": 2}}
```

- `timestamp` in UTC, ISO 8601 with milliseconds.
- `extra` holds the data the code passed with `extra={...}`, nested under its own key so that it never clashes with a
  field of the line; it is absent when there is none. A value JSON cannot hold (a UUID, a `Decimal`) is written as
  its string.
- `exception` holds the traceback of a `logger.exception(...)`.

With `json` on the CLI, stderr carries JSON lines only: the progress display stays silent, and the results still go
to stdout. One known limit: the error messages the commands print themselves (`Error: …`, `User not found …`) stay
plain lines on stderr, which an aggregator ingests as raw text.

## Writing a log

- `logger = logging.getLogger(__name__)`. Levels: `ERROR` unrecoverable, `WARNING` handled but unexpected, `INFO`
  milestones only, `DEBUG` the flow.
- **The message stands alone.** `console` and `rich` never print `extra`, so a warning carries its context (status
  code, step, track) in its text.
- **`extra` for the data worth querying** (IDs, counts, costs): only the `json` handler ships it, to be filtered or
  summed in an aggregator.
- **Never a secret**: log IDs, never tokens or passwords.
- In an `except` block, the traceback carries an unexpected error: `logger.exception(...)`, or
  `logger.warning(..., exc_info=True)` when the run goes on; the message gives the context. An expected error that
  its message explains (a rate limit, a rejected query) logs no traceback.

## `--verbose` is not `DEBUG`

| | `--verbose` | `DEBUG` logs |
|---|---|---|
| Reader | The user who wants to understand a result | The developer looking for a cause |
| Set by | An option of the commands that have details to show | The environment (`-l DEBUG`, settings) |
| Source | The progress events and the results | `logger.debug(...)` in the code |
| Shows | The LLM usage per step and model; for `playlist discover` / `explore`, the artists, searches and picks of each attempt | The flow: catalogue queries, each track excluded and why, the LLM replies |

A detail the user needs never hides in a `DEBUG` line, and a `--verbose` detail never only repeats a log.

The terminal output reads in blocks: a step with its details, a panel, a table, the cost line. One blank line sets a
block apart from the next, never inside one, never two in a row. Log lines print between the blocks as they come.
