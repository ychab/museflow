# Discovery: from titles to artists

In November 2026, discovery changed how it asks the LLM for music. It used to ask for tracks; it now asks for
**artists**, then lets the model choose among their real tracks. The change made playlists more relevant, three
times faster and almost three times cheaper, and it removed a whole subsystem along the way. This page tells why.

## The problem: a model knows artists, not discographies

Discovery asked the model for `artist – title` pairs, then searched each one in the Spotify catalogue. Two failures
followed from it, whatever the model:

- **Invented titles.** A model knows niche artists and their style, but not their discography: it writes a plausible
  title that does not exist. With a cheap model, about half the suggestions were lost that way.
- **The canon.** A stronger model invented almost nothing, but stayed with the best-known tracks of the genre: only
  about a third of its real tracks were new to me. Every playlist used up more of that canon, so the next one found
  even less, and playlists ended below their size.

I spent weeks narrowing the gap: matching title variants, a looser search when the strict one found nothing, a
stricter artist match. Each fix was real and measured. None moved the ceiling, which was the model's knowledge of
track titles.

## The insight

Checking the lost suggestions by hand showed one thing every time: **the artist was real, and it fitted the
request.** The model is reliable at choosing artists. So discovery now uses it for that, and lets the catalogue
supply what the model is bad at.

```mermaid
flowchart LR
    A[The model names artists,<br/>with the sound wanted] --> B[The catalogue gives<br/>their real tracks]
    B --> C[Tracks I already know<br/>are dropped, locally]
    C --> D[The model picks<br/>among what is left]
    D --> E[Playlist]
```

The model never writes a title any more: it picks real tracks by an id, so nothing can be invented, and it never
sees a track I already know, so it cannot suggest one.

## The measure

Same prompt, same model (Sonnet 5.5), several runs per method. Details and raw counts:
[issue #174](https://github.com/ychab/museflow/issues/174).

| | Titles (before) | Artists (now) |
|---|---|---|
| Rounds to fill a 10-track playlist | 2 to 3 | 1 |
| Tracks new to me, among the real ones found | 51% | 100% |
| Cost per playlist | $0.15 | $0.05 to $0.06 |
| Time per playlist | about 1m50 | about 40 s |

The targeted cases said the same:

- **A narrow request** (a genre in one language): the title method retried the canon three times and found **no**
  new track at all; the artist method filled the playlist in one round, for a third of the cost.
- **A niche genre**: the title method put most of its suggestions on one artist, and the playlist ended short; the
  artist method spread over a dozen artists.
- **Three real playlists in a row** on the same theme: each filled in one round, without repeating a track, and
  plenty of candidates were still left for the next.

By ear, the playlists were on par with the old ones, with one standout find. Listening also showed a bias, fixed
before the switch: seeing only titles, the model picked tracks whose title echoed the theme, whatever their sound.
It now gets each album's release year and is told to judge the sound, never the words.

## Why it matters for the product

The choice was not made on code elegance. It was made on what a listener gets:

- **More relevant.** Every track exists and is new to me, by construction, not by luck. A discovery playlist that
  repeats what I know is a failed playlist.
- **Faster.** About 40 seconds instead of two minutes: discovery is interactive, I wait for it.
- **Cheaper.** About a third of the cost per playlist. In the [business model sketch](business-model.md), playlists
  are the cheap, frequent part of the product: their unit cost is the one that scales with use.

## What I threw away

Keeping both methods would have meant two discovery pipelines to maintain, sharing little code, for a method that
lost on every measure. So the title method went: its prompt, the fuzzy matching of suggested titles to catalogue
tracks, its search, and the fuzzy-matching library itself. That is several weeks of measured work, removed on
purpose, for the same reason as the [V1 → V2 pivot](pivot.md): it served an approach I no longer believe in.

It is not lost: the last state of the title method is tagged `archive/discover-by-titles` in git. If a future model
writes reliable titles, the archive and #174 say exactly what was tried, and how it was measured.

## Honest status

- **Measured on one listener**: my runs, my library, a handful of themes.
- **The model picks without hearing.** It judges a track by its title, album and year, and leaves out what it cannot
  place. Letting me listen to samples before the playlist is created is an idea for later (#178).
- **A request leads only on what it settles.** Asked for a calm sound, the model used to lean toward the energy my
  profile shows. Now the request wins on the sound it implies, and a genre with its own sound decides which artists
  come in; the profile keeps the rest, and a request like "US rap" is answered from the profile alone (#177). On a
  niche genre, 0 of 5 playlists were on theme before, 2 of 3 after. The profile's languages then still broke ties and
  brought in a few artists of my usual scene, given a made-up sound; without that tie-break, 3 runs out of 3 kept to
  the genre (#184). The genre is the model's reading of it, which may not be mine; and on a genre far from my profile
  (calm acoustic folk), the playlist fits the theme but no longer sounds like me.
- **The same artists come back** across runs on one theme, deeper into their catalogue each time. That will run out
  one day; how the model reacts then is still to see.
