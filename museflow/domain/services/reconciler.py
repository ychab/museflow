import logging
from typing import Final

from rapidfuzz import fuzz

from museflow.domain.entities.track import Track
from museflow.domain.entities.track import TrackSuggested
from museflow.domain.types import ScoreReconciler
from museflow.domain.utils.text import normalize_text
from museflow.domain.value_objects.track import TrackNormalized

logger = logging.getLogger(__name__)


class Reconciler:
    """Domain service responsible for reconciling tracks using fuzzy text matching."""

    def __init__(self, match_threshold: float = 80.0) -> None:
        self.MATCH_THRESHOLD: Final[float] = match_threshold
        self.BASE_NAME_WEIGHT: Final[float] = 0.95

    def reconcile(
        self,
        track_suggested: TrackSuggested,
        candidates: list[Track],
    ) -> tuple[Track, ScoreReconciler] | None:
        """Finds the best canonical match for a suggested track in the provider's library."""

        track_target = TrackNormalized.create(
            name=track_suggested.name,
            artists=track_suggested.artists,
        )

        # Scores are 0.0 when a component is below MATCH_THRESHOLD, otherwise between MATCH_THRESHOLD and 100.
        # A best score of 0.0 therefore means no candidate matched.
        best_match: Track | None = None
        best_score = -1.0
        # The candidate closest to a match, kept apart from the best one: when all are rejected, it tells why.
        closest: tuple[Track, float, float] | None = None

        for candidate in candidates:
            track_score, artist_score = self._compute_similarity_scores(track_target=track_target, candidate=candidate)
            score = self._compute_reconciliation_score(track_score=track_score, artist_score=artist_score)
            if score > best_score:
                best_score = score
                best_match = candidate
            if closest is None or track_score + artist_score > closest[1] + closest[2]:
                closest = (candidate, track_score, artist_score)

        if best_match and best_score > 0.0:
            logger.debug(
                f"Matched '{track_suggested.primary_artist} - {track_suggested.name}' "
                f"-> '{best_match.name}' (Score: {best_score:.1f})"
            )
            return best_match, min(best_score / 100.0, 1.0)

        closest_detail = (
            f"Closest candidate: '{closest[0]}' (track: {closest[1]:.1f}, artist: {closest[2]:.1f})"
            if closest
            else "No candidate"
        )
        logger.debug(
            f"Reconciliation failed for '{track_suggested.primary_artist} - {track_suggested.name}'. "
            f"Best score: {best_score:.1f}. {closest_detail}",
            extra={"artists": track_suggested.artists, "track": track_suggested.name, "best_score": best_score},
        )
        return None

    def filter_by_artist(self, artist: str, candidates: list[Track]) -> list[Track]:
        """Keeps the candidates crediting `artist`, by exact normalized name: a short name must not match a longer one."""
        target = normalize_text(artist)
        kept = [candidate for candidate in candidates if target in {normalize_text(a) for a in candidate.artists}]

        rejected = {candidate.primary_artist for candidate in candidates if candidate not in kept}
        if rejected:
            logger.debug(f"Artist '{artist}': rejected candidates of {sorted(rejected)}")
        return kept

    def _compute_similarity_scores(self, track_target: TrackNormalized, candidate: Track) -> tuple[float, float]:
        """Returns the fuzzy similarity (0 to 100) of the track names, then of the closest artist names."""

        track_candidate = TrackNormalized.create(
            name=candidate.name,
            artists=candidate.artists,
        )

        # A title may differ only by an extra, e.g. "(Interlude)" or " - Bonus Track": the main parts count too,
        # slightly below a full match, so that the exact title wins when the search returns both.
        track_score = max(
            fuzz.token_sort_ratio(track_target.name, track_candidate.name),
            fuzz.token_sort_ratio(track_target.name_base, track_candidate.name_base) * self.BASE_NAME_WEIGHT,
        )
        artist_scores = [fuzz.WRatio(ta, ca) for ta in track_target.artists for ca in track_candidate.artists]
        best_artist_score = max(artist_scores) if artist_scores else 0.0

        return track_score, best_artist_score

    def _compute_reconciliation_score(self, track_score: float, artist_score: float) -> float:
        """Calculates a composite score, or 0.0 when the track or the artist is below the threshold."""

        if track_score < self.MATCH_THRESHOLD or artist_score < self.MATCH_THRESHOLD:
            return 0.0

        # Base composite: 60% track name weight, 40% artist name weight
        return (track_score * 0.6) + (artist_score * 0.4)
