# `enrich` commands

Add genre, mood and language metadata to tracks with an LLM, and back it up. Enrichment powers the `--genre`,
`--mood` and `--locale` filters of [`playlist history`](playlist.md#playlist-history).

## `enrich tracks`

Enriches tracks with AI-inferred genre, mood and locales (sung languages) metadata.

```bash
museflow enrich tracks --email <email> [OPTIONS]
```

| Option | Default | Description |
| --- | --- | --- |
| `--email` | required | User email address. |
| `--only-genre` | off | Enrich genre tags only. |
| `--only-mood` | off | Enrich mood labels only. |
| `--only-locale` | off | Enrich locales (sung languages) only. |
| `--force` | off | Re-enrich tracks that already have the requested fields. |
| `--batch-size` | `200` | Number of tracks per LLM request. |
| `--model` | `OPENROUTER_ENRICHER__MODEL` | OpenRouter model id for this run (e.g. `google/gemini-2.5-flash-lite`). It must support structured outputs. |
| `--limit` | none | Maximum number of tracks to process. |

Without any `--only-*` flag, all three fields are enriched. The flags can be combined. By default only tracks
missing a requested field are processed, so the command is safe to re-run after a new import.

**Prerequisites.** Imported tracks and an OpenRouter API key (`OPENROUTER_API_KEY`). This command calls the LLM: use `--limit` to try it
on a small sample first.

Genres follow a three-level taxonomy (macro genre, sub-genre, optional micro tag), moods are picked among 12
labels, and the locales are the ISO 639-1 codes of every language sung in the track. A track with no sung language (instrumental, or no reliable signal) gets an empty list and is not sent to the model again unless you pass `--force`. See the
[allowed values](playlist.md#genre-and-mood-values).

**Examples**

```bash
museflow enrich tracks --email user@example.com --limit 200
museflow enrich tracks --email user@example.com --only-mood --force
museflow enrich tracks --email user@example.com --limit 20 --model openai/gpt-5-mini
```

**Output.** `Enriched N track(s).`, plus a warning when some batches failed (details are in the logs, and a
re-run processes the missing tracks), or `No tracks to enrich.`.

## `enrich export`

Exports the genres, moods and locales of all enriched tracks to a YAML file, keyed by track fingerprint.

```bash
museflow enrich export --email <email> --output <path>
```

| Option | Default | Description |
| --- | --- | --- |
| `--email` | required | User email address. |
| `--output` | required | Path to the output YAML file. |

**Output.** `Exported enrichment for N track(s) to <path>`.

## `enrich import`

Restores genres, moods and locales from a YAML file produced by `enrich export`, without calling the LLM.

```bash
museflow enrich import --email <email> --input <path>
```

| Option | Default | Description |
| --- | --- | --- |
| `--email` | required | User email address. |
| `--input` | required | Path to the input YAML file. |

Tracks must already exist in the library.

**Output.** `Imported enrichment for N track(s) (K fingerprints not found in DB).`.
