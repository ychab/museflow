# `playlist` commands

Generate playlists, from the AI taste profile (`discover`) or from the listening history itself (`history`),
and manage them.

| Command | LLM call | Purpose |
| --- | --- | --- |
| [`playlist discover`](#playlist-discover) | Yes | New music guided by a taste profile. |
| [`playlist explore`](#playlist-explore) | Yes | The tracks you don't know from your favourite artists. |
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
| `--verbose` | off | Show the details of each round (artists suggested, their searches, the picks) and the LLM usage per step and model instead of a one-line total. |
| `--limit` | `10` | Target number of tracks in the generated playlist (1 to 30). |

The tuning lives in settings: the advisor is asked for `--limit` × `DISCOVERY_ADVISOR_LIMIT_RATIO` (1.5) artists,
then may pick as many tracks, `DISCOVERY_ARTIST_TRACKS_PAGES` (2) search pages of 10 tracks are read per artist,
`DISCOVERY_MAX_ATTEMPTS` (3) rounds at most, and `DISCOVERY_MAX_TRACKS_PER_ARTIST` (3) tracks per artist, a featured
appearance included.

**Naming an artist.** The advisor reads what the prompt asks of an artist it names. "Tracks of Artist X I don't know"
asks for that artist's own tracks: Artist X is suggested even if your library already covers them, their whole
catalogue is searched (on Spotify, one search per release year range, `DISCOVERY_REQUESTED_ARTIST_TRACKS_PAGES` pages
of 10 each, `SPOTIFY_SEARCH_CONCURRENCY` at a time), their tracks are not capped per artist, and a prompt naming only
artists gets only them, in a single round. "Something that sounds like Artist X" uses the artist as a sound reference: the
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

**Output.** While it runs, one line per finished step on stderr, grouped by round: artists suggested, catalogue
searched (the tracks you don't know), tracks picked (and how many the playlist keeps after the per-artist cap), then
the playlist created; each line gives its duration and, for an advisor step, its cost. Then the advisor's reasoning,
the table of discovered tracks (artist, track, album), and unless `--dry-run` is set, the playlist name and follow-up
commands to view and rate it; a warning follows when fewer tracks than `--limit` were found. Last, one line gives the
LLM calls, their cost and the elapsed time, even when no new track was found; with `--verbose`, an `LLM usage` table
details the calls, tokens, cost and time of each advisor step (`advisor_artists`, `advisor_picks`).

With `--verbose`, each step line is followed by its details: the artists suggested (score, `requested` for an artist
the prompt names, the sound wanted), what the catalogue search of each artist gave (tracks found, those crediting the
artist, those you don't know; `search rejected` when the provider refused the query), and the tracks picked, `cut`
when the per-artist cap or the limit leaves one out:

```text
Attempt 1/3
 ✓ Artists suggested   2 · Late-night jazz rap                      4.1s · $0.0123
   Nova Lane       0.92  warm Rhodes, slow tempo
   The Quiet Owls  0.85  requested  dusty loops
 ✓ Catalogue searched  9 unknown track(s) · 1/2 artists             2.8s
   Nova Lane       50 found · 38 by the artist · 9 unknown
   The Quiet Owls  20 found · 20 by the artist · 0 unknown
 ✓ Tracks picked       2 → 1/10 kept                                5.6s · $0.0201
   0.95  Nova Lane - Midnight Tram
   0.71  Nova Lane - Paper Moon  cut
```

## `playlist explore`

Plays the tracks you missed from the artists you already love: `history` replays what you know, `discover` brings new
artists, `explore` brings the unknown tracks of your own artists. No LLM call chooses the artists: they come from your
data, the artists you rate at or above your mean first (a Bayesian average, `STATS_BAYESIAN_CONFIDENCE`), then the
ones you play most; an artist you rate below your mean is left out. No taste profile is needed.

```bash
museflow playlist explore [PROMPT] [--email <email>] [OPTIONS]
```

| Argument / option | Default | Description |
| --- | --- | --- |
| `PROMPT` | none | Optional request on the sound wanted ("calm and acoustic"). The artists still come from your data. |
| `--email` | `MUSEFLOW_CLI_DEFAULT_EMAIL` | User email address. |
| `--provider` | `spotify` | The music provider to use. |
| `--model` | `OPENROUTER_ADVISOR__MODEL` | OpenRouter model id for this run, checked as for `discover`. |
| `--title` | `[MF] - Explore - <timestamp>` | Playlist name, used as is. |
| `--dry-run` | off | Explore tracks without creating a playlist. Still searches the provider catalogue. |
| `--verbose` | off | Show the details of each round (the searches of the favourites, the picks) and the LLM usage per step and model instead of a one-line total. |
| `--limit` | `10` | Target number of tracks in the generated playlist (1 to 30). |

The best `EXPLORE_ARTISTS_LIMIT` (20) favourites not blacklisted are shuffled, so that two runs start with other
artists, and each round takes the next `EXPLORE_ARTISTS_PER_ATTEMPT` (5). Their whole catalogue is searched as for an
artist a `discover` prompt names (one search per release year range, `DISCOVERY_REQUESTED_ARTIST_TRACKS_PAGES` pages
each, one artist at a time by default, `EXPLORE_ARTISTS_CONCURRENCY`, as each search already runs
`SPOTIFY_SEARCH_CONCURRENCY` queries at once), and the advisor picks among the tracks you don't know, guided by up to 5 of your best-rated tracks of each
artist. One LLM call per round; a round usually fills the playlist, and another one runs with the next artists until
`--limit` tracks are kept, `DISCOVERY_MAX_ATTEMPTS` is reached or no favourite is left. Tracks stay capped per artist
(`DISCOVERY_MAX_TRACKS_PER_ARTIST`), so the playlist mixes several of them.

**Prerequisites**

- Rated tracks ([`rate`](rate.md)) or an imported history ([`tracks history`](tracks.md#tracks-history)), so that
  your favourite artists are known.
- A connected Spotify account and an OpenRouter API key, as for `discover`.

**Examples**

```bash
museflow playlist explore
museflow playlist explore "calm and acoustic" --dry-run
museflow playlist explore --limit 20 --title "Missed favourites"
```

**Output.** As for `discover`, without the artists step nor the reasoning: one line per finished step and round, the
table of explored tracks, the playlist name unless `--dry-run` is set, and the LLM cost line. With `--verbose`, the
searches of the round's favourites and the picks are detailed as for `discover`, and the `LLM usage` table shows the
step `advisor_exploration_picks`.
The playlist is saved with the `explore` type, and its LLM usage under the `explore` operation.

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

Lists the playlists of a user, all of them or one type only.

```bash
museflow playlist list [--email <email>] [--type <type>]
```

| Option | Default | Description |
| --- | --- | --- |
| `--email` | `MUSEFLOW_CLI_DEFAULT_EMAIL` | User email address. |
| `--type` | none | Filter by playlist type: `discovery`, `explore` or `history`. |

**Output.** A table with ID, name, type (`discovery`, `explore` or `history`), prompt, focus and creation date, or a
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
| `--type` | none | Filter by playlist type: `discovery`, `explore` or `history` (only valid with `--purge`). |
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
