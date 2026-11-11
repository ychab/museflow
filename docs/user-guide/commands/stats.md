# `stats` commands

Read-only rankings computed locally from the library, with no LLM call. Ratings improve them but are not
required, except where noted.

## `stats artists`

Shows top artists ranked by an overall score combining breadth (distinct tracks), depth (plays) and quality
(ratings).

```bash
museflow stats artists [--email <email>] [OPTIONS]
```

| Option | Default | Description |
| --- | --- | --- |
| `--email` | `MUSEFLOW_CLI_DEFAULT_EMAIL` | User email address. |
| `--source` | `all` | Track source to include: `all`, `history` or `discovery`. |
| `--score-min` | none | Minimum score filter (0-10). |
| `--score-max` | none | Maximum score filter (0-10). |
| `--confidence` | `5` | Bayesian confidence constant: artists with fewer rated tracks than this are pulled toward the mean. |
| `--sort` | `overall` | Ranking strategy: `track_count`, `plays_count`, `rate_avg`, `quality` or `overall`. |
| `--limit` | `20` | Max rows in the table. |

**Sort strategies**

- `track_count`: number of distinct tracks.
- `plays_count`: total number of plays.
- `rate_avg`: plain average of the ratings.
- `quality`: average rating pulled toward the global mean for artists with few rated tracks, controlled by
  `--confidence`.
- `overall`: logarithm of the track count, times the logarithm of the play count, times the quality ratio.

**Example**

```bash
museflow stats artists --source history --sort plays_count --limit 10
```

**Output.** A _Top Artists_ table with rank, artist, quality, average rating, number of rated tracks, number of
tracks and plays (and the overall score when sorting by `overall`). Unrated artists show `—`.

## `stats candidates`

Shows artists worth exploring further: few tracks in the library but a high average score.

```bash
museflow stats candidates [--email <email>] [OPTIONS]
```

| Option | Default | Description |
| --- | --- | --- |
| `--email` | `MUSEFLOW_CLI_DEFAULT_EMAIL` | User email address. |
| `--limit` | `20` | Max rows in the table. |
| `--source` | `all` | Track source to include: `all`, `history` or `discovery`. |
| `--max-tracks` | `5` | Maximum total tracks for an artist to be a candidate. |
| `--min-avg` | `7.0` | Minimum average score for an artist to be a candidate. |

**Example**

```bash
museflow stats candidates --max-tracks 3 --min-avg 8
```

**Output.** A _Discovery Candidates_ table (artist, average score, rated tracks, total tracks), or
`No discovery candidates found.`. Requires rated tracks.

## `stats tags`

Shows top genres, moods or locales, with the scores of [`stats artists`](#stats-artists): the tags the enrichment
stored on the tracks, ranked from the library alone. A ground truth to check the taste profile against.

```bash
museflow stats tags [--email <email>] [OPTIONS]
```

| Option | Default | Description |
| --- | --- | --- |
| `--email` | `MUSEFLOW_CLI_DEFAULT_EMAIL` | User email address. |
| `--by` | `genre` | Tags to rank: `genre`, `mood` or `locale`. |
| `--tier` | none | Genre tier to rank: `macro`, `meso` or `micro`. With `--by genre` only. |
| `--source` | `all` | Track source to include: `all`, `history` or `discovery`. |
| `--score-min` | none | Minimum score filter (0-10). |
| `--score-max` | none | Maximum score filter (0-10). |
| `--confidence` | `5` | Bayesian confidence constant: tags with fewer rated tracks than this are pulled toward the mean. |
| `--sort` | `overall` | Ranking strategy, as for `stats artists`: `track_count`, `plays_count`, `rate_avg`, `quality` or `overall`. |
| `--limit` | `20` | Max rows in the table. |

A track counts in each of its tags. The enrichment orders the genres of a track from the broadest to the most
specific (macro, meso, then micro when it has one): without `--tier`, every genre counts; with it, only the genre at
that tier. The quality is pulled toward the mean rating of the whole library, as for the artists.

**Example**

```bash
museflow stats tags --by genre --tier macro --sort quality
```

**Output.** A _Top Genres_ (_Top Moods_, _Top Locales_) table with the columns of `stats artists`, the tag instead
of the artist, then how many tracks have no tag of that kind (not enriched yet), which the table leaves out:
`12 tracks without genre are not ranked.`. Run [`enrich tracks`](enrich.md#enrich-tracks) to tag them.

## `stats tracks`

Shows top rated tracks.

```bash
museflow stats tracks [--email <email>] [OPTIONS]
```

| Option | Default | Description |
| --- | --- | --- |
| `--email` | `MUSEFLOW_CLI_DEFAULT_EMAIL` | User email address. |
| `--score-min` | none | Minimum score filter (0-10). |
| `--score-max` | none | Maximum score filter (0-10). |
| `--sort` | `score` | Ranking strategy: `score` or `played_count`. |
| `--limit` | `20` | Max rows in the table. |

**Output.** A _Top Tracks_ table (artist, track, score, play count), or `No rated tracks found.`.
