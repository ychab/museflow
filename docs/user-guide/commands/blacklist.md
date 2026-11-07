# `blacklist` commands

Manage artists and tracks that must never appear in discovery playlists. Entries are also created from the
follow-up questions of the [`rate`](rate.md) prompts.

## `blacklist add-artist`

Adds one or more artists to the blacklist.

```bash
museflow blacklist add-artist <artist_name> [<artist_name> ...] [--email <email>]
```

| Argument / option | Default | Description |
| --- | --- | --- |
| `artist_names` | required | Artist name(s) to blacklist. |
| `--email` | `MUSEFLOW_CLI_DEFAULT_EMAIL` | User email address. |

**Example**

```bash
museflow blacklist add-artist "Some Artist" "Another Artist"
```

**Output.** One `Blacklisted artist: <name> (id: <uuid>)` line per artist.

## `blacklist add-track`

Adds a single track to the blacklist.

```bash
museflow blacklist add-track <name> --artist <artist_name> [--email <email>]
```

| Argument / option | Default | Description |
| --- | --- | --- |
| `name` | required | Track name. |
| `--artist` | required | Artist name. |
| `--email` | `MUSEFLOW_CLI_DEFAULT_EMAIL` | User email address. |

**Example**

```bash
museflow blacklist add-track "Some Track" --artist "Some Artist"
```

**Output.** `Blacklisted track: <name> by <artist> (id: <uuid>)`.

## `blacklist list`

Lists all blacklisted artists and tracks.

```bash
museflow blacklist list [--email <email>]
```

| Option | Default | Description |
| --- | --- | --- |
| `--email` | `MUSEFLOW_CLI_DEFAULT_EMAIL` | User email address. |

**Output.** A _Your Blacklist_ table with ID, type, artist name and track name, or `Your blacklist is empty.`.
The IDs are the ones expected by `blacklist remove`.

## `blacklist remove`

Removes one or more entries by ID.

```bash
museflow blacklist remove <id> [<id> ...] [--email <email>]
```

| Argument / option | Default | Description |
| --- | --- | --- |
| `item_ids` | required | Blacklist entry ID(s), as shown by `blacklist list`. |
| `--email` | `MUSEFLOW_CLI_DEFAULT_EMAIL` | User email address. |

**Output.** `Removed N blacklist entry(ies).`.

## `blacklist purge`

Deletes the entire blacklist. This cannot be undone.

```bash
museflow blacklist purge [--email <email>] [--yes]
```

| Option | Default | Description |
| --- | --- | --- |
| `--email` | `MUSEFLOW_CLI_DEFAULT_EMAIL` | User email address. |
| `--yes`, `-y` | off | Skip confirmation prompt. |

**Output.** A confirmation prompt (unless `--yes`), then `Deleted N blacklist entries of <email>.`.

## `blacklist export`

Exports the blacklist to a YAML file. Entries are stored by name, so the file can be restored after a database reset,
or edited by hand.

```bash
museflow blacklist export [--email <email>] --output <path>
```

| Option | Default | Description |
| --- | --- | --- |
| `--email` | `MUSEFLOW_CLI_DEFAULT_EMAIL` | User email address. |
| `--output` | required | Path to the output YAML file. |

**File format**

```yaml
artists:
  - artist_name: Some Artist
tracks:
  - name: Some Track
    artist_name: Another Artist
```

**Output.** `Exported N artist(s) and M track(s) to <path>`.

## `blacklist import`

Adds the entries of a YAML file produced by `blacklist export`. Entries already blacklisted (same name, whatever the
case or accents) are kept as they are and counted, so running the import twice changes nothing.

```bash
museflow blacklist import [--email <email>] --input <path>
```

| Option | Default | Description |
| --- | --- | --- |
| `--email` | `MUSEFLOW_CLI_DEFAULT_EMAIL` | User email address. |
| `--input` | required | Path to the input YAML file. |

The import is saved as a whole: an invalid entry (empty name, track without artist) rejects the whole file.

**Output.** `Imported N artist(s) and M track(s) (K already blacklisted).`.
