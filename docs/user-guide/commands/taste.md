# `taste` commands

Build and manage master taste profiles: an LLM analysis of the library (musical eras, personality archetype,
life-phase insights) that guides [`playlist discover`](playlist.md#playlist-discover).

## `taste build`

Builds a master taste profile from the library.

```bash
museflow taste build --email <email> --name <name> [OPTIONS]
```

| Option | Default | Description |
| --- | --- | --- |
| `--email` | required | User email address. |
| `--name` | required | Profile name (unique per user). |
| `--resume` / `--no-resume` | `--no-resume` | Resume from last checkpoint. |
| `--rated-only` / `--no-rated-only` | `--no-rated-only` | Restrict seed tracks to only those the user has explicitly rated (score 0-10). |
| `--track-limit` | `3000` | Max seed tracks to build the profile (1 to 20000). |
| `--batch-size` | `200` | Batch sizes for profiles (1 to 1000). |
| `--segment-model` | `OPENROUTER_PROFILER_SEGMENT__MODEL` | OpenRouter model id for the per-batch segment step (e.g. `google/gemini-3.1-flash-lite`). |
| `--merge-model` | `OPENROUTER_PROFILER_MERGE__MODEL` | OpenRouter model id for the step merging each segment into the profile. |
| `--reflect-model` | `OPENROUTER_PROFILER_REFLECT__MODEL` | OpenRouter model id for the final reflection step. |

**Prerequisites**

- Tracks imported with [`tracks history`](tracks.md#tracks-history).
- An OpenRouter API key (`OPENROUTER_API_KEY`). This command calls the LLM and is the most expensive step of the
  flow.

Each step's model must support structured outputs: the command checks the three models against the OpenRouter catalog
before any call, and stops with a suggestion on a typo.

Without `--rated-only`, all tracks are candidates and rated ones are annotated with their score. With it, only
rated tracks seed the profile, which is useful once a significant part of the library has been
[rated](rate.md).

If a build is interrupted (rate limit, network), the command stops with `Build paused at batch X/Y` and exits
with an error. Run the same command again with `--resume` to continue from the checkpoint. This also applies if the final reflection step fails (reported as the last batch, e.g. `3/3`): only that step is repeated.

**Example**

```bash
museflow taste build --email user@example.com --name my-profile --track-limit 1500
museflow taste build --email user@example.com --name test --track-limit 200 --reflect-model anthropic/claude-sonnet-4.5
```

**Output.** `Taste profile built: N tracks processed`, then the profile name, the logic version, the model of each
step (segment, merge, reflect), the number of eras, the personality archetype and the life-phase insights.

## `taste list`

Lists all taste profiles of a user.

```bash
museflow taste list --email <email>
```

| Option | Default | Description |
| --- | --- | --- |
| `--email` | required | User email address. |

**Output.** A table with ID, name, logic version, status, tracks and last update, or `No taste profiles found.`.
A profile whose build was paused shows an in-progress status and cannot be used for discovery until completed.

## `taste view`

Displays one profile in detail.

```bash
museflow taste view --email <email> --name <name> [--format json|python|html]
```

| Option | Default | Description |
| --- | --- | --- |
| `--email` | required | User email address. |
| `--name` | required | Profile name (unique per user). |
| `--format` | `json` | Output format: `json`, `python`, or `html` (browser). |

**Example**

```bash
museflow taste view --email user@example.com --name my-profile --format html
```

`html` writes a report to a file and opens it in the default browser.

## `taste export`

Exports a profile to a YAML file, for backup or transfer.

```bash
museflow taste export --email <email> --name <name> --output <path>
```

| Option | Default | Description |
| --- | --- | --- |
| `--email` | required | User email address. |
| `--name` | required | Profile name (unique per user). |
| `--output` | required | Path to the output YAML file. |

**Output.** `Taste profile '<name>' exported to <path>`.

## `taste import`

Imports a profile from a YAML file produced by `taste export`.

```bash
museflow taste import --email <email> --input <path>
```

| Option | Default | Description |
| --- | --- | --- |
| `--email` | required | User email address. |
| `--input` | required | Path to the input YAML file. |

**Output.** `Taste profile '<name>' imported successfully.`. A missing file or invalid YAML ends with an error.
