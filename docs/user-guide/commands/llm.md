# `llm` commands

Look back at what the LLM calls cost. Every paid command (`taste build`, `playlist discover`, `enrich tracks`) saves
its tokens and cost when it ends, whatever the outcome: a paused build or a failed discovery was billed too. See
[Cost tracking](../../technical/llm-pipeline.md#cost-tracking) for what is counted.

## `llm usage`

Sums the saved LLM usage, one row per group, then the total. It reads the local database only and costs nothing.
Without `--email`, it sums all the users: the overview of an instance. `MUSEFLOW_CLI_DEFAULT_EMAIL` does not apply here.

```bash
museflow llm usage [--email <email>] [--operation taste_build|discover|enrich] [--since YYYY-MM-DD] [--until YYYY-MM-DD]
                   [--by operation|model|effort|step|month|profile|user|run ...]
```

| Option | Default | Description |
| --- | --- | --- |
| `--email` | all the users | User email address. |
| `--operation` | all | Only the runs of this command: `taste_build`, `discover` or `enrich`. |
| `--since` | none | Only the runs from this date on, in UTC. |
| `--until` | none | Only the runs up to this date included, in UTC. |
| `--by` | `operation` | How to group the rows (see below). Repeat it to combine groupings: one row per combination, one column per grouping. Each grouping may be given once. |

| `--by` | One row per | Order |
| --- | --- | --- |
| `operation` | command: `taste_build`, `discover`, `enrich` | most expensive first |
| `model` | model OpenRouter actually served, fallbacks included | most expensive first |
| `effort` | reasoning effort asked for the step: `minimal`, `low`, `medium`, `high`… | most expensive first |
| `step` | pipeline step: `advisor`, `enricher`, `profiler segment`, `profiler merge`, `profiler reflect` | most expensive first |
| `month` | calendar month, in UTC | chronological |
| `profile` | taste profile the run built or used; `(none)` for an enrichment or a deleted profile. Without `--email`, prefixed with the user's email (`user@example.com / evening`), since profile names are unique per user only | most expensive first |
| `user` | user's email; only without `--email` | most expensive first |
| `run` | command run, shown by its start (UTC), e.g. `2026-11-03 10:20:51`; add `--by operation` or `--by profile` to see what it was | chronological |

With several groupings, the rows are sorted level by level, in the `--by` order: `--by model --by effort` puts the
most expensive model first, then its efforts, most expensive first, whatever the other models' efforts cost.

**Examples**

```bash
museflow llm usage --email user@example.com --by month --since 2026-01-01
museflow llm usage --by model --by effort --operation enrich
museflow llm usage --by month --by model --since 2026-09-01 --until 2026-11-30
museflow llm usage --by user
museflow llm usage --email user@example.com --by run --by operation --since 2026-11-01
```

**Output.** A `LLM usage` table with one column per grouping, the runs (command executions), the calls, the prompt,
completion and reasoning tokens, the cost in dollars and the time spent waiting for the model, then a `Total` row: the
grand total, without subtotals. A run that spans several groups (a build calls several steps) counts once in the total.
With `--by run`, each row is one run: the runs column is left out and the total reads `Total (<n> runs)`.
`No LLM usage recorded.` when nothing matches.

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
skipped, so importing twice adds nothing. Each row keeps its date, so `--by month` and `--since` give the same
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
