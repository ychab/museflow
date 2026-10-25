# `blacklist` commands

Manage artists and tracks that must never appear in discovery playlists. Entries are also created from the
follow-up questions of the [`rate`](rate.md) prompts.

## `blacklist add-artist`

Adds one or more artists to the blacklist.

```bash
museflow blacklist add-artist <artist_name> [<artist_name> ...] --email <email>
```

| Argument / option | Default | Description |
| --- | --- | --- |
| `artist_names` | required | Artist name(s) to blacklist. |
| `--email` | required | User email address. |

**Example**

```bash
museflow blacklist add-artist "Some Artist" "Another Artist" --email user@example.com
```

**Output.** One `Blacklisted artist: <name> (id: <uuid>)` line per artist.

## `blacklist add-track`

Adds a single track to the blacklist.

```bash
museflow blacklist add-track <name> --artist <artist_name> --email <email>
```

| Argument / option | Default | Description |
| --- | --- | --- |
| `name` | required | Track name. |
| `--artist` | required | Artist name. |
| `--email` | required | User email address. |

**Example**

```bash
museflow blacklist add-track "Some Track" --artist "Some Artist" --email user@example.com
```

**Output.** `Blacklisted track: <name> by <artist> (id: <uuid>)`.

## `blacklist list`

Lists all blacklisted artists and tracks.

```bash
museflow blacklist list --email <email>
```

| Option | Default | Description |
| --- | --- | --- |
| `--email` | required | User email address. |

**Output.** A _Your Blacklist_ table with ID, type, artist name and track name, or `Your blacklist is empty.`.
The IDs are the ones expected by `blacklist remove`.

## `blacklist remove`

Removes one or more entries by ID.

```bash
museflow blacklist remove <id> [<id> ...] --email <email>
```

| Argument / option | Default | Description |
| --- | --- | --- |
| `item_ids` | required | Blacklist entry ID(s), as shown by `blacklist list`. |
| `--email` | required | User email address. |

**Output.** `Removed N blacklist entry(ies).`.

## `blacklist purge`

Deletes the entire blacklist. This cannot be undone.

```bash
museflow blacklist purge --email <email> [--yes]
```

| Option | Default | Description |
| --- | --- | --- |
| `--email` | required | User email address. |
| `--yes`, `-y` | off | Skip confirmation prompt. |

**Output.** A confirmation prompt (unless `--yes`), then `Deleted N blacklist entries.`.
