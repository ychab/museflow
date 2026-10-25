# `rate` commands

Give tracks a score from 0 to 10. Scores are an explicit preference signal: they feed `taste build --rated-only`,
the `--score-min` / `--score-max` / `--sort score` options of [`playlist history`](playlist.md#playlist-history),
the [`stats`](stats.md) commands, and the blacklist prompts.

Both interactive commands (`history` and `playlist`) behave the same way. For each track the prompt is:

```text
[3/10] Some Artist — Some Track [played: 42x]
  Rate (0-10, s=skip, u=permanently skip) [s]:
```

| Input | Effect |
| --- | --- |
| `0` to `10` | Saves the score. |
| `s` (default, or Enter) | Skips the track for now; it will be proposed again later. |
| `u` | Permanently skips the track: it will not be proposed again. |

When the score is at or below the blacklist threshold (setting `DISCOVERY_BLACKLIST_SCORE_THRESHOLD`, default
`3`), two follow-up questions offer to blacklist the track and its artist (see
[`blacklist`](blacklist.md)). Ratings and blacklist entries are saved when the session ends.

## `rate history`

Interactively rates unrated history tracks, ordered by play count (most played first).

```bash
museflow rate history --email <email> [OPTIONS]
```

| Option | Default | Description |
| --- | --- | --- |
| `--email` | required | User email address. |
| `--limit` | `10` | Maximum number of tracks to rate. |
| `--reset` | off | Clear all existing history track scores before rating. |
| `--play` | off | Play each track before rating. |
| `--play-provider` | `spotify` | Provider to use for playback. Requires `--play`. |
| `--artist` | none | Filter by primary artist (case-insensitive). |

**Prerequisites.** Imported history. For `--play`, a connected Spotify account and an **active Spotify device**
(the desktop or mobile app open, or a web player). When no device is found, the command warns and retries; if
the device is still unavailable it stops the session.

**Example**

```bash
museflow rate history --email user@example.com --play --limit 25
```

**Output.** The prompts above, then `Saved N rating(s). X track(s) and Y artist(s) blacklisted. Z track(s)
permanently skipped.`, or `No unrated history tracks.`. With `--reset`, a confirmation is asked first and the
number of cleared scores is printed.

## `rate playlist`

Interactively rates the tracks of a discovery playlist, or, when no playlist is given, the queue of all unrated
discovery tracks.

```bash
museflow rate playlist [playlist_id] --email <email> [OPTIONS]
```

| Argument / option | Default | Description |
| --- | --- | --- |
| `playlist_id` | none | Playlist UUID to rate. |
| `--email` | required | User email address. |
| `--limit` | `20` | Max unrated tracks to show (queue mode only). |
| `--play` | off | Play each track before rating. |
| `--play-provider` | `spotify` | Provider to use for playback. Requires `--play`. |

**Examples**

```bash
museflow rate playlist --email user@example.com --play
museflow rate playlist 3f2b8c1e-0000-4000-8000-000000000000 --email user@example.com
```

**Output.** Same prompts and summary as `rate history`, or `No unrated discovery tracks.`.

## `rate export`

Exports ratings (and permanent skips) to a YAML file. Tracks are identified by fingerprint, so the file can be
restored after a database reset.

```bash
museflow rate export --email <email> --output <path>
```

| Option | Default | Description |
| --- | --- | --- |
| `--email` | required | User email address. |
| `--output` | required | Path to the output YAML file. |

**Output.** `Exported N rated track(s) and M permanently skipped track(s) to <path>`.

## `rate import`

Restores ratings from a YAML file produced by `rate export`.

```bash
museflow rate import --email <email> --input <path>
```

| Option | Default | Description |
| --- | --- | --- |
| `--email` | required | User email address. |
| `--input` | required | Path to the input YAML file. |

Tracks must already exist in the library (import the history first).

**Output.** `Imported N score(s) and M permanent skip(s) (K fingerprints not found in DB).`.
