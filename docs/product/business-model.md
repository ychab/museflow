# Business model sketch

!!! info "Read this as a thought exercise"
    MuseFlow is a personal proof of concept. There is no company, no pricing page and no plan to launch. But thinking
    about how a product *could* sustain itself is part of building it, and it already influenced technical decisions.

## Where the cost is

MuseFlow has almost no infrastructure cost: a PostgreSQL database and a small API. The real variable cost is **LLM
usage**, and it is very unevenly distributed:

| Operation | How often | LLM work | Relative cost |
|---|---|---|---|
| Build a taste profile | Rarely (when taste shifts, a few times a year) | Thousands of tracks in batches, then merge and synthesis with stronger models | **High** |
| Tag tracks (genres, moods, language) | Once per new track | Many small requests on the cheapest model | Low, one-off |
| Generate a discovery playlist | Often | One or a few requests using the profile | **Low** |
| Rediscovery playlist | Often | None — a database query | Nil |

I have not measured costs rigorously (see [lessons learned](lessons-learned.md)). From memory, a full profile build
over a large history cost me **a few euros**, varying a lot with the models chosen and the number of seed tracks —
I managed to bring it down by moving the high-volume steps to cheaper models. A playlist costs a fraction of that.

The one thing I am sure of: **the profile is expensive; playlists are cheap.**

## A pricing idea that follows the cost

That asymmetry suggests a simple model:

- **Pay for the profile.** Building (or rebuilding) a taste profile is the premium moment. It is also the moment
  with the most perceived value: people love reading a portrait of themselves.
- **Include playlists in the subscription.** The margin on profiles absorbs a number of discovery playlists per
  month, depending on the tier.
- **Rediscovery is free.** It costs nothing to run and is the best hook for long-time listeners.

## Why the product can exist next to the platforms

- **The data access is a legal right**, not a partnership. A platform can close an API; it cannot refuse a GDPR
  export to its own users.
- **The provider is only an output.** MuseFlow needs to search tracks and write playlists. If that disappeared, the
  playlist could still be exported as a plain list (not implemented today) — degraded, but alive.

## The elephant in the room

For the listener, MuseFlow is complementary: people keep their streaming subscription. For the platform, it is not.
**MuseFlow competes head-on with the platform's own recommendation engine**, and the platform controls the output
side: its API terms, how many users a third-party app may serve, and whether that app keeps its access at all. A
platform that sees MuseFlow as competition can switch it off for every future user.

Presenting it as "a tool to build a musical profile, not a recommender" would be playing with words. It would not
hold up in court, let alone against a platform's legal team. The plain-list fallback keeps the product technically
alive, but a list you have to search track by track is barely usable, and nobody is going to build a streaming
platform to get around it.

So, plainly: **as a business, this idea is close to dead on arrival.** I would not expect an investor to follow me
on it, and I would rather say so than sell a dream. As a product exercise, that constraint is precisely what made it
worth building: it forced the question of what a product can rely on when it does not own its distribution.

## Why I did not go further

Three honest reasons. First, my goal was to build something that works *for me* before thinking about anyone else.
Second, LLM pricing and capabilities change every few months; a detailed financial model would be obsolete before
being useful. Third, the platform risk above would weigh on any serious plan. The architecture keeps the options open — swappable LLM vendor, cheap models where possible,
checkpointed expensive jobs — and that is the part I could act on today.
