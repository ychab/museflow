# Recipes

Task-oriented examples. They assume the [getting started](index.md) steps are done (user created, Spotify
connected, history imported) and use `user@example.com` as the account.

## Rediscover forgotten favourites

Tracks that were loved but have not been played for a long time. Rate some of the history first (see the next
recipe), then filter on score and on the last play date.

```bash
museflow playlist history \
  --email user@example.com \
  --score-min 7 \
  --played-last-max 2023-12-31 \
  --limit 30
```

By default, tracks already used in a previous history playlist are excluded, so running the command again
gives a fresh selection. Add `--sort score` to order by rating instead of play count, or `--group-by-artists`
to keep an artist's tracks together. Without any rating, drop `--score-min` and rely on the play count alone.

## Rate your history while listening

```bash
museflow rate history --email user@example.com --play --limit 20
```

Each track plays on the active Spotify device and a score between 0 and 10 is asked for. Enter `s` to skip a
track for now, `u` to never be asked about it again. Tracks are proposed from the most played, and a low score
offers to blacklist the track or the artist. Restrict the session to one artist with `--artist`. See
[`rate`](commands/rate.md).

## A playlist for a mood or a language

From the library, with enriched tracks ([`enrich tracks`](commands/enrich.md#enrich-tracks) first):

```bash
museflow playlist history --email user@example.com --mood chill --genre jazz --locale en --dry-run
```

`--genre`, `--mood` and `--locale` can be repeated and match any of the given values (OR logic) within the
same filter, while different filters are combined (AND). Remove `--dry-run` once the preview looks right.

For new music instead, give the advisor a hint:

```bash
museflow playlist discover --email user@example.com --genre electronic --mood energetic
```

## Preview before creating

Both playlist commands accept `--dry-run`: the tracks are listed in a table and nothing is saved or created on
Spotify.

```bash
museflow playlist history --email user@example.com --score-min 8 --dry-run
museflow playlist discover --email user@example.com --focus roots_revival --dry-run
```

`discover --dry-run` still calls the LLM; `history --dry-run` does not.

## Keep an artist out of your playlists

```bash
museflow blacklist add-artist "Some Artist" --email user@example.com
museflow blacklist list --email user@example.com
```

Blacklisted artists and tracks are excluded from discovery. To undo, pass the ID shown by `blacklist list`:

```bash
museflow blacklist remove 3f2b8c1e-0000-4000-8000-000000000000 --email user@example.com
```

See [`blacklist`](commands/blacklist.md).

## Back up and restore ratings, enrichment and taste profiles

Ratings and LLM results are the only data that cannot be recomputed from the Spotify export for free. Export
them to YAML:

```bash
museflow rate export   --email user@example.com --output backup/ratings.yaml
museflow enrich export --email user@example.com --output backup/enrichment.yaml
museflow taste export  --email user@example.com --name my-profile --output backup/my-profile.yaml
```

After a database reset, re-import the history first, then restore (no LLM call, no cost):

```bash
museflow tracks history --email user@example.com --directory ~/Downloads/MySpotifyData
museflow rate import    --email user@example.com --input backup/ratings.yaml
museflow enrich import  --email user@example.com --input backup/enrichment.yaml
museflow taste import   --email user@example.com --input backup/my-profile.yaml
```

Ratings and enrichment are matched by track fingerprint, so tracks missing from the library are reported as
"not found" and skipped.

## Find artists worth exploring

```bash
museflow stats candidates --email user@example.com --max-tracks 3 --min-avg 8
museflow stats artists --email user@example.com --sort quality --limit 10
```

See [`stats`](commands/stats.md).

## Clean up after experiments

```bash
museflow playlist delete --email user@example.com --purge --type discovery --include-remote
museflow tracks delete --email user@example.com --source discovery --purge
```

The first command removes discovery playlists locally and on Spotify; the second removes the discovery tracks
from the library. Both ask for confirmation unless `--yes` is given. See
[`playlist delete`](commands/playlist.md#playlist-delete) and [`tracks delete`](commands/tracks.md#tracks-delete).
