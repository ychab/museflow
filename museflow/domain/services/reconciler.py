import logging
from typing import Final

from rapidfuzz import fuzz

from museflow.domain.entities.music import Track
from museflow.domain.entities.music import TrackSuggested
from museflow.domain.types import ScoreReconciler
from museflow.domain.value_objects.music import TrackNormalized

logger = logging.getLogger(__name__)


class Reconciler:
    """Domain service responsible for reconciling tracks using fuzzy text matching."""

    def __init__(self, match_threshold: float = 80.0, score_minimum: float = 60.0) -> None:
        self.MATCH_THRESHOLD: Final[float] = match_threshold
        self.SCORE_MINIMUM: Final[float] = score_minimum

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

        best_match: Track | None = None
        best_score = -1.0

        for candidate in candidates:
            score = self._compute_reconciliation_score(track_target=track_target, candidate=candidate)
            if score > best_score:
                best_score = score
                best_match = candidate

        if best_match and best_score >= self.SCORE_MINIMUM:
            logger.debug(
                f"Matched '{track_suggested.primary_artist} - {track_suggested.name}' "
                f"-> '{best_match.name}' (Score: {best_score:.1f})"
            )
            return best_match, min(best_score / 100.0, 1.0)

        logger.debug(
            f"Reconciliation failed for '{track_suggested.primary_artist} - {track_suggested.name}'. "
            f"Best score: {best_score:.1f}",
            extra={"artists": track_suggested.artists, "track": track_suggested.name, "best_score": best_score},
        )
        return None

    def _compute_reconciliation_score(self, track_target: TrackNormalized, candidate: Track) -> float:
        """Calculates a composite score using fuzzy name and artist matching."""

        track_candidate = TrackNormalized.create(
            name=candidate.name,
            artists=candidate.artists,
        )

        track_score = fuzz.token_sort_ratio(track_target.name, track_candidate.name)
        artist_scores = [fuzz.WRatio(ta, ca) for ta in track_target.artists for ca in track_candidate.artists]
        best_artist_score = max(artist_scores) if artist_scores else 0.0

        if track_score < self.MATCH_THRESHOLD or best_artist_score < self.MATCH_THRESHOLD:
            return 0.0

        # Base composite: 60% track name weight, 40% artist name weight
        return (track_score * 0.6) + (best_artist_score * 0.4)
