# `llm` commands

Look back at what the LLM calls cost. Every paid command (`taste build`, `playlist discover`, `enrich tracks`) saves
its tokens and cost when it ends, whatever the outcome: a paused build or a failed discovery was billed too. See
[Cost tracking](../../technical/llm-pipeline.md#cost-tracking) for what is counted.

## `llm usage`

Sums the saved LLM usage, one row per group, then the total. It reads the local database only and costs nothing.
Without `--email`, it sums all the users: the overview of an instance.

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
| `model` | model OpenRouter actually served, fallbacks included | most expensive first |
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
reasoning tokens, and the cost in dollars, then a `Total` row. A run that spans several groups (a build calls several
steps) counts once in the total. `No LLM usage recorded.` when nothing matches.

!!! note
    The history lives in the database only: a database reset wipes it.
