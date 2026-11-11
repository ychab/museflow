# `llm` commands

Look back at what the LLM calls cost. Every paid command (`taste build`, `playlist discover`, `enrich tracks`) saves
its tokens and cost when it ends, whatever the outcome: a paused build or a failed discovery was billed too. See
[Cost tracking](../../technical/llm-pipeline.md#cost-tracking) for what is counted.

## `llm usage`

Sums the saved LLM usage, one row per group, then the total. It reads the local database only and costs nothing.
Without `--email`, it sums all the users: the overview of an instance. `MUSEFLOW_CLI_DEFAULT_EMAIL` does not apply here.

```bash
museflow llm usage [--email <email>] [--by operation|model|step|month|profile|user|run] [--since YYYY-MM-DD]
```

| Option | Default | Description |
| --- | --- | --- |
| `--email` | all the users | User email address. |
| `--by` | `operation` | How to group the rows (see below). |
| `--since` | none | Only the runs from this date on, in UTC. |

| `--by` | One row per | Order |
| --- | --- | --- |
| `operation` | command: `taste_build`, `discover`, `enrich` | most expensive first |
| `model` | model OpenRouter actually served, fallbacks included, and its reasoning effort: `google/gemini-3.8-flash (low)`, the model alone when the effort is the provider's default | most expensive first |
| `step` | pipeline step: `advisor`, `enricher`, `profiler segment`, `profiler merge`, `profiler reflect` | most expensive first |
| `month` | calendar month, in UTC | chronological |
| `profile` | taste profile the run built or used; `(none)` for an enrichment or a deleted profile. Without `--email`, prefixed with the user's email (`user@example.com / evening`), since profile names are unique per user only | most expensive first |
| `user` | user's email; only without `--email` | most expensive first |
| `run` | command run: its start (UTC), operation and profile, then the user's email without `--email`, e.g. `2026-11-03 10:20:51 discover evening` | chronological |

**Examples**

```bash
museflow llm usage --email user@example.com --by month --since 2026-01-01
museflow llm usage --by user
museflow llm usage --email user@example.com --by run --since 2026-11-01
```

**Output.** A `LLM usage` table with the group, the runs (command executions), the calls, the prompt, completion and
reasoning tokens, the cost in dollars and the time spent waiting for the model, then a `Total` row. A run that spans several groups (a build calls several
steps) counts once in the total. `No LLM usage recorded.` when nothing matches.

!!! note
    The history lives in the database: a database reset wipes it. Export it first with [`llm export`](#llm-export).

## `llm export`

Exports the user's LLM usage history to a YAML file, one entry per row: run, operation, step, model, reasoning effort,
tokens, cost, time and date. The profile travels by name, the playlist link is dropped (playlists are not exported).

```bash
museflow llm export [--email <email>] --output <path>
```

| Option | Default | Description |
| --- | --- | --- |
| `--email` | `MUSEFLOW_CLI_DEFAULT_EMAIL` | User email address. |
| `--output` | required | Path to the output YAML file. |

**Output.** `Exported <n> LLM usage row(s) to <path>`.

## `llm import`

Imports a file produced by `llm export`, in one transaction. A row already there (same run, step and model) is
skipped, so importing twice adds nothing. A file without the reasoning effort (exported before it was recorded)
imports with the provider's default. Each row keeps its date, so `--by month` and `--since` give the same
figures as before the export. The profile link is restored when a profile of that name exists: import the profiles
first ([`taste import`](taste.md#taste-import)).

```bash
museflow llm import [--email <email>] --input <path>
```

| Option | Default | Description |
| --- | --- | --- |
| `--email` | `MUSEFLOW_CLI_DEFAULT_EMAIL` | User email address. |
| `--input` | required | Path to the input YAML file. |

**Output.** `Imported <n> LLM usage row(s) (<m> already there).`. A missing file or invalid YAML ends with an error.
