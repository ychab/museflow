# Product principles

These principles were not written up front. They emerged from decisions I had to make, and I wrote them down
afterwards. Each one points to the change that embodies it, so you can check the reasoning against the code.

## 1. The user's data comes first, and only what is needed

MuseFlow is built on the streaming history the user exports through their GDPR rights, not on what a provider's API
is willing to expose (see [the pivot](pivot.md)).

That data is personal, so the import keeps the **minimum** needed: track name, artist, album, track ID and play
timestamp. The export also contains IP addresses, country of connection and device information. MuseFlow drops them
at parse time; they never reach the database.

## 2. Quality over quantity

V1 produced long playlists, and I discarded almost all of them. V2 goes the other way:

- **Fewer, more confident suggestions.** Default sizes went down (20 → 10 suggestions per call, 30 → 10 tracks per
  playlist), and the LLM is told to only include a track it is confident about, *and not to pad* the list to reach
  a number. Five great tracks beat twenty guesses.
- **A cap on tracks per artist.** A small constraint with a big perceived effect: a "discovery" playlist with four
  songs from the same artist does not feel like discovery.
- **Confidence on both sides.** The LLM gives a confidence score; matching its suggestion to a real catalogue track
  gives another. Within a band of similar LLM confidence, a well-matched track ranks above a fuzzy match. A great
  suggestion that resolves to the wrong song is worse than a good one that resolves to the right song.
- **Never suggest the same track twice.** Every suggested track is remembered and excluded from future runs.

## 3. The user is the best judge

Streaming platforms *infer* taste from behaviour: plays, skips, saves. Behaviour is noisy — you skip because you are
busy, you let a playlist run because your hands are full. MuseFlow *asks*:

- **Ratings from 0 to 10** on any track — from discovery playlists or from the history itself, with an option to
  play each track while rating it.
- **A blacklist** of artists and tracks that must never come back, which survives profile rebuilds.
- **A permanent skip** for tracks that can no longer be played (removed from the catalogue), so they stop coming up.

Ratings feed the taste profile (rated tracks can even be the only seed) and the discovery prompts. Nobody knows what I
love better than I do; the product's job is to make telling it cheap.

## 4. Constrain the LLM where it hallucinates

Asking an LLM for "the genres of this track" gives creative answers: synonyms, invented sub-genres, inconsistent
spellings. Useful as prose, useless as data you can filter on.

So genres, moods and language are **closed vocabularies**: a fixed three-level genre taxonomy (macro, meso and micro
genres), a fixed list of moods, and ISO language codes with an explicit instruction not to guess. Values outside the
lists are dropped. A smaller vocabulary with reliable values is worth more than a rich one you cannot trust — it is
what makes "a playlist of my top-rated melancholic tracks in Spanish" possible.

## 5. Independence from any single vendor

The pivot moved MuseFlow off a dependency on one music provider's API. The same reasoning applies to the LLM:
everything that calls a model sits behind a port (profiler, advisor, enricher), so the vendor can be swapped. The
calls now go through the OpenRouter gateway: each step can use any model it lists, from any vendor, with a setting or a
CLI flag. Thanks to the ports, the switch from direct Gemini calls replaced the adapters and left the use cases
untouched.

## 6. The right model for the right job

Not every LLM call deserves the most expensive model:

- **High-volume, simple tasks** (summarising batches of history, tagging thousands of tracks) use the cheapest
  "lite" model.
- **Synthesis tasks** (merging partial profiles, writing the final portrait) use stronger models — but only once.

Gemini was the first choice for its **cost-to-context ratio**: a generous free tier and a context window large enough
to send hundreds of tracks per request. Its models are still the defaults, now reached through OpenRouter, which also
lets a step move to a cheaper or better model the day one is found. Structured output mattered too, but any serious
model supports it nowadays.

## 7. Fail gracefully, resume cheaply

Long LLM jobs fail: rate limits, timeouts, truncated answers. A failure should not cost the work already paid for.

- Building a taste profile is **checkpointed**: if it stops, `--resume` continues from the last batch instead of
  starting over (and paying again).
- **Self-healing structured output.** When the LLM returns an invalid structured answer, MuseFlow sends it back the
  error and asks it to fix it, a few times, before giving up — and logs it, so I can measure whether it is worth it.
- Provider rate limits are respected, but with a ceiling: if a provider asks to wait too long, the command stops with
  a clear message rather than hanging.
