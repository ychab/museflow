# `playlist` commands

Generate playlists, from the AI taste profile (`discover`) or from the listening history itself (`history`),
and manage them.

| Command | LLM call | Purpose |
| --- | --- | --- |
| [`playlist discover`](#playlist-discover) | Yes | New music guided by a taste profile. |
| [`playlist history`](#playlist-history) | No | A "best of" from tracks already in the library. |
| [`playlist list`](#playlist-list) | No | List playlists. |
| [`playlist view`](#playlist-view) | No | Show a playlist and its ratings. |
| [`playlist delete`](#playlist-delete) | No | Delete one or many playlists. |

## `playlist discover`

Discovers new tracks guided by the taste profile and saves them as a playlist. The advisor picks artists, the
music provider gives their real tracks, and the advisor then chooses among the ones you don't know yet: every track
exists, and none is already in your library.

```bash
museflow playlist discover [PROMPT] [--email <email>] [OPTIONS]
```

| Argument / option | Default | Description |
| --- | --- | --- |
| `PROMPT` | none | Optional freeform request for the advisor: genres, moods, a theme, in your own words (several genres or moods fit in one sentence). Without it, the advisor follows the profile and the focus. |
| `--email` | `MUSEFLOW_CLI_DEFAULT_EMAIL` | User email address. |
| `--provider` | `spotify` | The music provider to use. |
| `--name` | latest profile | Taste profile name (defaults to latest). |
| `--focus` | `expansion` without a prompt, none with one | The discovery focus strategy: `expansion`, `roots_revival` or `cultural_bridge`. With a prompt, no focus is applied unless given: it would pull the advisor away from the requested theme. |
| `--model` | `OPENROUTER_ADVISOR__MODEL` | OpenRouter model id for this run (e.g. `google/gemini-3.5-flash`). It must support structured outputs: the command checks the model against the OpenRouter catalog before any call, and stops with a suggestion on a typo. |
| `--title` | advisor's suggestion | Playlist name, used as is. Without it, the playlist is named `[MF] - <name suggested by the advisor> - <timestamp>`. |
| `--dry-run` | off | Discover tracks without creating a playlist. Still searches the provider catalogue, so a connected provider is required. |
| `--limit` | `10` | Target number of tracks in the generated playlist (1 to 30). |

The tuning lives in settings: the advisor is asked for `--limit` × `DISCOVERY_ADVISOR_LIMIT_RATIO` (1.5) artists,
then may pick as many tracks, `DISCOVERY_ARTIST_TRACKS_PAGES` (2) search pages of 10 tracks are read per artist,
`DISCOVERY_MAX_ATTEMPTS` (3) rounds at most, and `DISCOVERY_MAX_TRACKS_PER_ARTIST` (3) tracks per artist, a featured
appearance included.

**Naming an artist.** The advisor reads what the prompt asks of an artist it names. "Tracks of Artist X I don't know"
asks for that artist's own tracks: Artist X is suggested even if your library already covers them, their search goes
deeper (`DISCOVERY_REQUESTED_ARTIST_TRACKS_PAGES`, 5 pages), their tracks are not capped per artist, and a prompt
naming only artists gets only them, in a single round. "Something that sounds like Artist X" uses the artist as a sound reference: the
playlist holds other artists.

**Focus strategies**

- `expansion`: cousin genres that have not been explored yet.
- `roots_revival`: modern tracks that echo the oldest era of the profile.
- `cultural_bridge`: music at the intersection of the oldest and the current era.

**Prerequisites**

- A completed taste profile ([`taste build`](taste.md#taste-build)).
- A connected Spotify account ([`provider connect`](provider.md#provider-connect)).
- An OpenRouter API key (`OPENROUTER_API_KEY`).

One round is two LLM calls (the artists, then the picks); a round usually fills the playlist, and another one runs,
with other artists, until `--limit` tracks are picked or `DISCOVERY_MAX_ATTEMPTS` is reached. Tracks already in the
library, and blacklisted artists and tracks ([`blacklist`](blacklist.md)), are never offered to the advisor.

**Examples**

```bash
museflow playlist discover --limit 15
museflow playlist discover "chill jazz and soul, mostly instrumental" --dry-run
museflow playlist discover "lo-fi beats for a rainy evening" --title "Friday night"
museflow playlist discover "tracks of The Fictional Band I don't know"
museflow playlist discover --focus roots_revival
museflow playlist discover --dry-run --model anthropic/claude-sonnet-4.5
```

**Output.** A report table per round (artists asked, their tracks you don't know, tracks picked), then the table of
discovered tracks (artist, track, album). Unless `--dry-run` is set, the playlist is created and the command prints
its ID and follow-up commands to view and rate it. Last, an `LLM usage` table gives the calls, tokens, cost and time of
each advisor step (`advisor_artists`, `advisor_picks`), then the total and the elapsed time of the command, even when
no new track was found.

## `playlist history`

Creates a playlist from the history tracks already in the library, filtered and ordered by play count or
score. No LLM is involved.

```bash
museflow playlist history [--email <email>] [OPTIONS]
```

| Option | Default | Description |
| --- | --- | --- |
| `--email` | `MUSEFLOW_CLI_DEFAULT_EMAIL` | User email address. |
| `--provider` | `spotify` | The music provider to use. |
| `--name-suffix` | timestamp | Custom name suffix for the playlist (replaces the timestamp). |
| `--score-min` | none | Minimum track score (0-10). |
| `--score-max` | none | Maximum track score (0-10). |
| `--artist` | none | Filter by primary artist name. |
| `--genre` | none | Filter by genre tag (repeatable, OR logic). |
| `--mood` | none | Filter by mood tag (repeatable, OR logic). |
| `--locale` | none | Filter by sung language, ISO 639-1 (repeatable, matches any of the track's languages). |
| `--played-first-min` | none | Filter tracks first played on or after this date (YYYY-MM-DD). |
| `--played-first-max` | none | Filter tracks first played on or before this date (YYYY-MM-DD). |
| `--played-last-min` | none | Filter tracks last played on or after this date (YYYY-MM-DD). |
| `--played-last-max` | none | Filter tracks last played on or before this date (YYYY-MM-DD). |
| `--duplicate` | off | Allow tracks already used in a previous history playlist. |
| `--group-by-artists` | off | Group tracks by primary artist. |
| `--dry-run` | off | Preview matched tracks without creating a playlist. |
| `--sort` | `played_count` | Sort tracks by this field: `played_count` or `score`. |
| `--limit` | `20` | Maximum number of tracks in the playlist (at least 1). |

**Prerequisites**

- Tracks imported with [`tracks history`](tracks.md#tracks-history) and a connected Spotify account.
- `--genre`, `--mood` and `--locale` only match tracks that were [enriched](enrich.md).
- `--score-min` and `--score-max` only match tracks that were [rated](rate.md).

By default, tracks already present in a previous history playlist are left out, so each run yields fresh
tracks. Pass `--duplicate` to allow them again. Ranges are validated: `--score-min` cannot exceed
`--score-max`, and each `min` date cannot be after its `max`.

**Examples**

```bash
# Favourite tracks not heard for a while
museflow playlist history --score-min 7 --played-last-max 2024-01-01

# Preview electronic tracks without creating anything
museflow playlist history --genre electronic --genre pop --dry-run
```

**Output.** A table of matched tracks (artist, track, play count, score). With `--dry-run`, the command stops
with a notice that the playlist was not created. Otherwise it prints the saved playlist name and ID. If nothing
matches, it suggests trying `--duplicate`. `--dry-run` needs no provider connection, so it works even if you
have not run `museflow provider connect`.

### Genre and mood values

`--genre` accepts any tag of the three-level taxonomy (13 macro genres, 56 meso sub-genres, and about 100
micro tags, see `museflow playlist history --help` for the complete list). Macro and meso values:

| Macro genre | Meso sub-genres |
| --- | --- |
| `hip-hop` | `rap`, `trap`, `drill`, `boom-bap`, `lo-fi hip-hop` |
| `electronic` | `house`, `techno`, `drum-and-bass`, `ambient-electronic`, `trance`, `dubstep` |
| `rock` | `indie-rock`, `alternative-rock`, `punk`, `hard-rock`, `grunge`, `post-rock`, `progressive-rock`, `psychedelic-rock` |
| `pop` | `synth-pop`, `electro-pop`, `dance-pop`, `indie-pop`, `k-pop` |
| `r-n-b` | `contemporary-r-n-b`, `neo-soul`, `funk`, `trap-soul` |
| `jazz` | `jazz-fusion`, `smooth-jazz`, `bebop`, `nu-jazz` |
| `classical` | `baroque`, `romantic-era`, `contemporary-classical` |
| `reggae` | `roots-reggae`, `dancehall`, `dub` |
| `country` | `outlaw-country`, `folk-country`, `bluegrass` |
| `latin` | `reggaeton`, `salsa`, `cumbia`, `bossa-nova`, `latin-pop`, `flamenco` |
| `metal` | `heavy-metal`, `black-metal`, `death-metal`, `nu-metal`, `thrash-metal`, `doom-metal` |
| `folk` | `indie-folk`, `acoustic-folk`, `singer-songwriter` |
| `world` | `afrobeats`, `arabic`, `balkan`, `celtic` |

`--mood` accepts: `energetic`, `chill`, `melancholic`, `upbeat`, `aggressive`, `romantic`, `focus`, `party`,
`introspective`, `euphoric`, `peaceful`, `dark`.

`--locale` is a two-letter ISO 639-1 language code, such as `en`, `fr` or `es`. A track can be sung in several languages (a duet, say), and it matches when any of them is in the list.

## `playlist list`

Lists all playlists of a user.

```bash
museflow playlist list [--email <email>]
```

| Option | Default | Description |
| --- | --- | --- |
| `--email` | `MUSEFLOW_CLI_DEFAULT_EMAIL` | User email address. |

**Output.** A table with ID, name, type (`discovery` or `history`), prompt, focus and creation date, or a
notice when there is no playlist.

## `playlist view`

Shows a playlist with its tracks and their ratings.

```bash
museflow playlist view <playlist_id> [--email <email>]
```

| Argument / option | Default | Description |
| --- | --- | --- |
| `playlist_id` | required | Playlist ID. |
| `--email` | `MUSEFLOW_CLI_DEFAULT_EMAIL` | User email address. |

**Output.** The playlist header, then a table of tracks with their position, ID, artists, name and score.

## `playlist delete`

Deletes one playlist, or many with `--purge`. By default only the local record is deleted; the playlist stays
in the provider account unless `--include-remote` is set.

```bash
museflow playlist delete [playlist_id] [--email <email>] [OPTIONS]
```

| Argument / option | Default | Description |
| --- | --- | --- |
| `playlist_id` | none | Playlist ID (required unless `--purge` is used). |
| `--email` | `MUSEFLOW_CLI_DEFAULT_EMAIL` | User email address. |
| `--purge` | off | Delete all matching playlists instead of a single one. |
| `--type` | none | Filter by playlist type: `discovery` or `history` (only valid with `--purge`). |
| `--provider` | none | Filter by provider (only valid with `--purge`). |
| `--include-remote` | off | Also unfollow/delete the playlist on the provider (e.g. Spotify). |
| `--yes`, `-y` | off | Skip confirmation prompt. |

Pass either a playlist ID or `--purge`, not both. `--type` and `--provider` require `--purge`.

**Example**

```bash
museflow playlist delete --purge --type history --include-remote
```

**Output.** Unless `--yes` is given, `--purge` asks for confirmation. Then `Deleted N playlist(s) of <email>.`.
Using `--include-remote` requires a connected account on the provider of each playlist deleted.

!!! note
    Deleting history playlists makes their tracks eligible again for the next `playlist history` run.
