import logging

from museflow.domain.entities.track import Track
from museflow.domain.utils.text import normalize_text

logger = logging.getLogger(__name__)


class Reconciler:
    """Domain service matching the catalogue tracks to the artist the advisor named."""

    def filter_by_artist(self, artist: str, candidates: list[Track]) -> list[Track]:
        """Keeps the candidates crediting `artist`, by exact normalized name: a short name must not match a longer one."""
        target = normalize_text(artist)
        kept = [candidate for candidate in candidates if target in {normalize_text(a) for a in candidate.artists}]

        rejected = {candidate.primary_artist for candidate in candidates if candidate not in kept}
        if rejected:
            logger.debug(f"Artist '{artist}': rejected candidates of {sorted(rejected)}")
        return kept
