# `tracks` commands

Import the streaming history and delete tracks from the library.

## `tracks history`

Imports the extended streaming history from JSON files (see [Spotify data export](../spotify-data-export.md)).

```bash
museflow tracks history --email <email> --directory <path> [OPTIONS]
```

| Option | Default | Description |
| --- | --- | --- |
| `--email` | required | User email address. |
| `--directory` | required | Directory containing streaming history JSON files. |
| `--provider` | `spotify` | Music provider to import streaming history from. |
| `--min-duration-played` | `90` | Minimum duration played in seconds to include. |
| `--batch-size` | `20` | Number of tracks to upsert per batch (1 to 500). |
| `--purge` / `--no-purge` | `--no-purge` | Purge existing tracks before import. |

**Prerequisites**

- The user exists.
- A directory containing the exported `Streaming_History_Audio_*.json` files. Other files of the export
  (video history, `Userdata.json`, ...) are ignored.

**Example**

```bash
museflow tracks history --email user@example.com --directory ~/Downloads/MySpotifyData --min-duration-played 30
```

**Output.** A green `Import successful in <n>s!` line and an _Import Streaming History Results_ table with
these rows: items read; items skipped (no timestamp, short play, no track ID); unique track IDs; tracks already
known; tracks play data updated; total play events; tracks created.

The import can be re-run with newer exports: existing tracks get their play data updated. Use `--purge` to
start from a clean library instead (this removes existing tracks of the provider first).

## `tracks delete`

Deletes tracks matching filters.

```bash
museflow tracks delete --email <email> (--artist <name> | --name <name> | --purge) [OPTIONS]
```

| Option | Default | Description |
| --- | --- | --- |
| `--email` | required | User email address. |
| `--artist` | none | Filter by primary artist name (case-insensitive). |
| `--name` | none | Filter by track name (case-insensitive). |
| `--source` | `all` | Filter by track source: `all`, `history` or `discovery`. |
| `--provider` | none | Filter by music provider (`spotify`). |
| `--purge` | off | Delete all tracks without artist/name filter. |
| `--yes`, `-y` | off | Skip confirmation prompt. |

At least one of `--artist`, `--name` or `--purge` is required.

**Example**

```bash
museflow tracks delete --email user@example.com --artist "Some Artist" --source history
```

**Output.** When filtering by artist only, the matching track names are listed. Unless `--yes` is given, a
prompt `About to delete N track(s). Continue?` must be confirmed. Then `Deleted N track(s).`, or
`No tracks found matching the filters.`.

!!! warning
    Deleting a track also deletes its rating and enrichment. Use [`rate export`](rate.md#rate-export) and
    [`enrich export`](enrich.md#enrich-export) first if they should be kept.
