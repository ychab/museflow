# Product

MuseFlow is a side project, but I built it the way I would build a product: starting from a problem, choosing what
to depend on, listening to the only user I had (me), and changing course when the evidence said so.

This section is about the *why* and the *what*. The *how* lives in the [technical section](../technical/index.md).

## In two minutes

- **The problem.** Streaming recommendations serve the platform's business as much as the listener.
  MuseFlow serves only the listener. → [Why MuseFlow](why.md)
- **The pivot.** V1 depended on the provider's API, and Spotify keeps closing the endpoints such a product needs: a
  lot of effort heading straight into a wall, and far from the provider-agnostic product I wanted. The suggestions
  were poor too. V2 is built on the one thing a provider cannot withhold: your own data, exported under the GDPR.
  → [The V1 → V2 pivot](pivot.md)
- **V3.** One AI vendor was the next single point of failure. MuseFlow now reaches most models on the market through
  one gateway: no vendor lock-in, a profile per model to compare, and a model chosen per step to control the cost.
  → [V3: any model](v3.md)
- **The principles.** Quality over quantity, the user as the judge, a constrained LLM, no single vendor.
  → [Product principles](principles.md)
- **The surprise.** Dogfooding showed that what I play most is not what I love most, and that rediscovering forgotten
  favourites mattered as much as discovering new music. → [What my data taught me](insights.md)
- **The money.** Profiles are expensive, playlists are cheap — a pricing idea follows. → [Business model sketch](business-model.md)
- **The failures.** What did not work, what I did not measure, and what I would do next. → [Lessons learned](lessons-learned.md)

## Reading path

If you only have five minutes, read [the pivot](pivot.md) and [lessons learned](lessons-learned.md). They say the most
about how I make decisions — and how I handle being wrong.
