# What my data taught me

I am MuseFlow's first user, and my own streaming history is its first dataset. Running the product on it changed
what I thought the product was for. The numbers below are aggregates from my own export; they are not a study, just
one listener's evidence — but they shaped real decisions.

## The dataset

| | |
|---|---|
| Period covered | 2017 → 2026 (9+ years) |
| Plays in the export | ~228,000 |
| Listening time | ~6,500 hours of music |
| Distinct tracks / artists | ~23,000 / ~3,700 |
| Tracks kept after filtering and aggregation | ~11,300 |
| Whole database dump | ~6 MB |

Every play becomes part of a **single row per track**: how many times it was played, when for the first time, when
for the last time. Hundreds of thousands of events compress into a table small enough to reason about — and small
enough to send, in batches, to an LLM.

## Insight 1: half of the "plays" are not listening

About **half of all plays last less than 90 seconds**, and almost 40% less than 30 seconds. Those are skips, previews,
"not now" moments. Counting them as signal would describe the algorithm's attempts more than my taste.

→ The import ignores plays below a minimum duration (configurable). It halves the raw data and makes what remains
much more meaningful.

## Insight 2: what I play most is not what I love most

When I started rating my own history, I expected my most-played tracks to be my favourites. They were not, not
reliably.

A play count measures *exposure* as much as *preference*. A track can climb because it sat in an algorithmic playlist
I left running while cooking, not because I chose it. **The algorithm decided a good part of my top tracks, not me.**

→ This is why ratings exist and why they weigh more than play counts in MuseFlow. It is also why the taste profile
can be built from rated tracks only.

## Insight 3: a long history is full of forgotten favourites

Looking at the history over time:

- **38%** of the tracks I played ten times or more had **not been played since before 2024**;
- about **a hundred tracks I rated 8/10 or more** had been dormant for over two years.

These are not discoveries. They are tracks I loved, that aged well, and that no recommendation engine ever brought
back — nothing in the platform's incentives rewards resurfacing a five-year-old track I already "consumed".

Rating them was a genuinely moving experience: I realised how much music I had forgotten, and how good much of it
still sounds.

→ This became a feature I had not planned: **rediscovery playlists**. Filter your own history by rating, genre, mood,
language, or by when you first or last played a track ("what did I love in 2019 and never play again?"), and push it
to your provider as a playlist. Previously generated rediscovery playlists are excluded, so each new one surfaces
different tracks.

## Insight 4: my usage drifted from discovery to rediscovery

MuseFlow was designed around *discovery*. Yet after I rebuilt my database in late June 2026, most of the playlists I
actually created were rediscovery playlists, and most of my time went into rating and tagging my history.

I did not fight that. It is the most valuable product signal I got: the problem I set out to solve (discover new
music) was real, but a neighbouring one (recover the music I already loved) turned out to be more pressing for me.
Providers have "throwback" features too, but they guess from behaviour; MuseFlow can rely on what I explicitly said.

It needs a long history to shine — ten years of listening, not one or two. That defines a niche, and I think that is
fine.

!!! warning "What these numbers do not say"
    They come from one person. And the metric that matters most for discovery — how many suggested tracks I actually
    keep — **was never measured** in V2. See [lessons learned](lessons-learned.md).

## See it on example profiles

The taste profile is the heart of MuseFlow. Rather than publishing mine, I built three fictional ones — a pop
listener, a rock listener and a rap listener — rendered with the same view the CLI produces:
[example taste profiles](examples/index.md).
