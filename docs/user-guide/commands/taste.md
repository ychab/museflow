# `taste` commands

Build and manage master taste profiles: an LLM analysis of the library (musical eras, personality archetype,
life-phase insights) that guides [`playlist discover`](playlist.md#playlist-discover).

## `taste build`

Builds a master taste profile from the library.

```bash
museflow taste build [--email <email>] --title <title> [--name <name>] [OPTIONS]
```

| Option | Default | Description |
| --- | --- | --- |
| `--email` | `MUSEFLOW_CLI_DEFAULT_EMAIL` | User email address. |
| `--title` | every profile | Profile title, as shown (`"Soirées d'hiver"`). |
| `--name` | the title as a slug (`soirees-d-hiver`) | Profile name keying it, unique per user: letters, digits, `-` and `_`, 64 at most, as it keys the profile in the API's URLs. |
| `--resume` / `--no-resume` | `--no-resume` | Resume from last checkpoint. |
| `--rated-only` / `--no-rated-only` | `--no-rated-only` | Restrict seed tracks to only those the user has explicitly rated (score 0-10): the periods are cut from their plays only. |
| `--track-limit` | `3000` | Max seed tracks to build the profile (1 to 20000), capped by the tracks played at least once. A track played in several periods takes a seed in each. |
| `--batch-size` | automatic | Seed tracks per listening period, one LLM request each (1 to 1000). By default 200, or the seeds split into about 20 periods for a larger library. |
| `--segment-model` | `OPENROUTER_PROFILER_SEGMENT__MODEL` | OpenRouter model id for the per-batch segment step (e.g. `google/gemini-3.1-flash-lite`). |
| `--merge-model` | `OPENROUTER_PROFILER_MERGE__MODEL` | OpenRouter model id for the step merging each segment into the profile. |
| `--reflect-model` | `OPENROUTER_PROFILER_REFLECT__MODEL` | OpenRouter model id for the final reflection step. |
| `--verbose` | off | Show the LLM usage per step and model instead of a one-line total. |

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
museflow taste build --title "My profile" --track-limit 1500
museflow taste build --title test --track-limit 200 --reflect-model anthropic/claude-sonnet-4.5
```

**Output.** While it runs, a progress bar on stderr counts the listening periods, then a live line follows the
reflection; each ends with a `✓` line giving its duration and cost. With `--resume`, a `↻ Resumed at 2/4 period(s),
from the checkpoint` line says where the build picks up. Then a panel shows the profile: its name, the personality
archetype, the tracks, eras and logic version, the eras with their time range, and the life-phase insights; a line
below gives the model of each step (segment, merge, reflect). Last, one line gives the LLM calls, their cost and the
elapsed time; with `--verbose`, an `LLM usage` table details the calls, tokens, cost and time per step and model. It is
printed after a pause too, since those calls were paid.

**Interrupting it.** Ctrl+C stops the build with exit code 130: the periods done are saved, and `--resume` continues
after them.

**One build per profile.** While a build runs, another build of the same profile name stops at once with an error,
before any LLM call. A build killed without stopping cleanly (machine shut down, `kill -9`) holds the name until its
lease expires, 15 minutes after its last saved period (`TASTE_PROFILE_BUILD_LEASE_MINUTES`); `--resume` works again
then.

## `taste list`

Lists all taste profiles of a user.

```bash
museflow taste list [--email <email>]
```

| Option | Default | Description |
| --- | --- | --- |
| `--email` | `MUSEFLOW_CLI_DEFAULT_EMAIL` | User email address. |

**Output.** A table with ID, name, logic version, status, tracks and last update, or `No taste profiles found.`.
A profile whose build was paused shows an in-progress status and cannot be used for discovery until completed.

## `taste view`

Displays one profile in detail.

```bash
museflow taste view [--email <email>] --name <name> [--format json|python|html]
```

| Option | Default | Description |
| --- | --- | --- |
| `--email` | `MUSEFLOW_CLI_DEFAULT_EMAIL` | User email address. |
| `--name` | every profile | Profile name (unique per user). |
| `--format` | `json` | Output format: `json`, `python`, or `html` (browser). |

**Example**

```bash
museflow taste view --name my-profile --format html
```

`html` writes a report to a file and opens it in the default browser.

## `taste delete`

Deletes one profile.

```bash
museflow taste delete [--email <email>] --name <name> [--yes]
```

| Option | Default | Description |
| --- | --- | --- |
| `--email` | `MUSEFLOW_CLI_DEFAULT_EMAIL` | User email address. |
| `--name` | every profile | Profile name (unique per user). |
| `--yes`, `-y` | `false` | Skip the confirmation prompt. |

**Output.** `Taste profile '<name>' of <email> deleted.`, or an error if no profile has that name. Discovery playlists built from
the profile are kept; they only lose their link to it. A paused build is deleted with its checkpoint.

!!! warning
    Recreating a profile takes a full LLM build. Run [`taste export`](#taste-export) first if you may need it again.

## `taste export`

Exports taste profiles to a YAML file, for backup or transfer: every profile of the user, or one with `--name`.

```bash
museflow taste export [--email <email>] [--name <name>] --output <path>
```

| Option | Default | Description |
| --- | --- | --- |
| `--email` | `MUSEFLOW_CLI_DEFAULT_EMAIL` | User email address. |
| `--name` | every profile | Profile name (unique per user). |
| `--output` | required | Path to the output YAML file. |

**Output.** `Exported <n> taste profile(s) to <path>: '<name>', ...`. The file is a list of profiles, even for one.

## `taste import`

Imports the profiles of a YAML file produced by `taste export`, in one transaction: all of them or none. A profile with
the same name is overwritten. A file holding a single profile (exported before the multi-profile export) is accepted
too.

```bash
museflow taste import [--email <email>] --input <path>
```

| Option | Default | Description |
| --- | --- | --- |
| `--email` | `MUSEFLOW_CLI_DEFAULT_EMAIL` | User email address. |
| `--input` | required | Path to the input YAML file. |

**Output.** `Imported <n> taste profile(s): '<name>', ...`. A missing file or invalid YAML ends with an error.
