# Lessons learned

I don't believe in project stories where everything went to plan. This one did not. Mistakes are where most of the
learning happened, so here they are, together with the current limits and what I would do next.

## What did not work

### Betting on a generous provider API (V1)

V1 was built on the assumption that Spotify's API would stay open and stable. It did not, and the suggestions it
produced were mostly discarded anyway (~95%, by my own estimate at the time). The lesson was not "APIs are bad" but
*identify which dependency can kill the product, and build on something it cannot take away*. That is the
[V1 → V2 pivot](pivot.md).

### "Similar tracks" from Last.fm

The first similarity engine came from Last.fm's "similar tracks". My V2 notes summed it up: an API that is barely
maintained, limited to historical data, and outperformed by an LLM working from a real taste profile. It was removed
in V2, along with the discovery flow that was its only consumer.

### Producer affinities: right idea, no data

In some genres, rap in particular, **the producer matters as much as the performer** — often more. A great
production carries an average performer; a weak one sinks a good performer. Spotify's song credits made me realise
that several producers I love were hiding behind tracks I had never connected, and helped me find new ones.

I built an experiment to add "producer affinities" to the taste profile and to discovery. The results were bad: LLMs
simply do not know reliably who produced what, and confidently invent it. The platforms have this data and keep it.
The experiment lives on an unmerged branch. If a reliable source of production credits becomes available, it would be
real value for genres where producers drive the sound — and would matter much less for bands that compose their own
music.

### Taste profiles that look smarter than they are

Reading my generated profiles closely, I found real defects:

- musical "eras" whose labels contradict their dates, or that overlap;
- recent eras spanning a few days while older ones span years;
- weights in the "core identity" shrinking towards zero as partial profiles are merged.

The prose reads well, which makes these errors easy to miss. Lesson: **an LLM output that sounds convincing still
needs structural checks.** Fixing the era segmentation and the merge logic is the first item on my list.

### Tools that did not stick

Not every experiment in my workflow was a success either: a local-model coding assistant (removed within the hour),
aider, and a code-packing tool for chat LLMs were all tried and dropped. See
[AI-assisted development](../technical/ai-assisted-development.md) for what remained.

## What I did not measure (and should have)

I kept no metrics. That is the biggest gap in this project as a *product*. In particular, the one number that defines
discovery quality — **how many suggested tracks I actually keep** — was never measured in V2. The feeling is that it
is far better than V1, mostly because known tracks are now properly excluded. A feeling is not a metric.

What I would instrument first:

| Metric | Why |
|---|---|
| Discovery keep rate (tracks rated ≥ 7 / tracks suggested) | The product's north star |
| Rating coverage of the history | Strength of the explicit signal behind each profile |
| Cost per profile build and per playlist | Validates (or kills) the [business model sketch](business-model.md) |
| Self-healing trigger rate on LLM answers | Tells whether the retry mechanism earns its complexity |
| Rediscovery playlists created vs discovery playlists | Confirms or refutes the usage drift I observed |

## Current limits, stated plainly

- **Privacy is POC-grade.** The import minimises personal data and no user identifier is sent to the LLM — only
  artist/title pairs, ratings and the profile. Prompts are only routed to Zero Data Retention endpoints, but that
  rests on the policies the providers declare. And users are identified by email in the database. A real product
  would need contractual guarantees or a self-hosted model, data retention rules and account deletion. Details in
  [privacy & data](../technical/privacy-and-data.md).
- **One LLM gateway.** The pivot reduced the dependency on the music provider and created one on the LLM provider.
  OpenRouter removed the lock-in on a model vendor and moved it to a gateway; the ports would let a direct vendor
  adapter come back if the gateway had to go.
- **One music provider.** Multi-provider history merge is possible by design, untested in practice.
- **Commands are not atomic, on purpose.** I first planned one transaction per command, then asked when atomicity
  is really needed: only when a partial state is *wrong*, not merely *incomplete*. Most commands produce an
  incomplete but valid state that a re-run completes, and committing step by step keeps paid LLM work. The real
  defect was ordering: discovery now creates the remote playlist before writing anything locally. Its two local
  writes (tracks and playlist) then share one transaction. A database failure right after a remote call can still
  leave an orphan playlist on the provider.
- **A session per command was the wrong scope.** Repositories committed on their own over one session per command,
  so a plain read reopened a transaction that stayed *idle in transaction* during the next Gemini call, holding
  locks that block migrations and the snapshot that VACUUM needs. Two patches came first: a small unit of work that
  swapped `commit` for `flush` on the shared session, then an explicit "release before a remote call" step, closed
  unmerged because nobody would think of calling it. The fix was structural: use cases now own short transactions
  through a classic unit of work (one session per `async with` block, repositories never commit), so a remote call
  inside a transaction is visible in the code instead of hidden behind a read. The full story is in
  [Why a unit of work](../technical/unit-of-work.md).
- **A CLI, not an app.** Perfect for me, a barrier for anyone else.
- **One application doing everything.** See below.

## If it grew: services, not one app

The codebase has become large, more than I would like for a single service. If MuseFlow were to grow seriously, I
would split it along the pipeline, each service owning one thing: history import, taste profiling, recommendations
and playlists, enrichment. The hexagonal ports already mark most of the seams.

I have not done it, deliberately. Running several services (and the cluster around them) costs money that a solo
side project cannot justify, and one person jumping between several repositories pays a real overhead. A
well-layered single application is the right shape for today; the split is a decision for when there is a team and
a reason.

## Ideas not explored yet

**Several profiles per listener.** This is more a hunch than a plan. Profiles are already named, and each one records
the profiler and the models that built it; discovery picks which profile to use. That opens questions I have not
explored: one profile per source (or per provider, once several histories are imported), one built from rated tracks
only, one per model. Different models already produce noticeably different portraits from the same history, and so
different suggestions. Tying playlists to the profile they came from, and comparing models through their profiles,
could become a way to choose a model on the result that matters rather than on a benchmark.

## What I would do next

1. Instrument the metrics above, starting with the discovery keep rate.
2. Fix the era segmentation and merge logic of the taste profile.
3. Compare models on quality *and* cost, now that the OpenRouter gateway makes each step a setting.
4. Only then, think about a UI.

## The meta-lesson

Progress on this project came through mistakes, rewrites and deleted code — not despite them. Perfection is out of
reach; getting a little closer every iteration is the job.
