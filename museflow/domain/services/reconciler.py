import logging
from typing import Final

from rapidfuzz import fuzz

from museflow.domain.entities.music import Track
from museflow.domain.entities.music import TrackSuggested
from museflow.domain.types import AlbumType
from museflow.domain.value_objects.music import TrackNormalized

logger = logging.getLogger(__name__)


class TrackReconciler:
    """Domain service responsible for reconciling tracks using fuzzy text matching and heuristics."""

    def __init__(self, match_threshold: float = 80.0, score_minimum: float = 60.0) -> None:
        self.MATCH_THRESHOLD: Final[float] = match_threshold
        self.SCORE_MINIMUM: Final[float] = score_minimum

    def reconcile(self, track_suggested: TrackSuggested, candidates: list[Track]) -> Track | None:
        """Finds the best canonical match for a suggested track in the provider's library."""

        track_target = TrackNormalized.create(
            name=track_suggested.name,
            artists=track_suggested.artists,
            duration_ms=track_suggested.duration_ms,
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
                f"Matched '{track_suggested.artists[0]} - {track_suggested.name}' "
                f"-> '{best_match.name}' (Score: {best_score:.1f})"
            )
            return best_match

        logger.warning(
            f"Reconciliation failed for '{track_suggested.artists[0]} - {track_suggested.name}'. "
            f"Best score: {best_score:.1f}",
            extra={"artists": track_suggested.artists, "track": track_suggested.name, "best_score": best_score},
        )
        return None

    def _compute_reconciliation_score(self, track_target: TrackNormalized, candidate: Track) -> float:
        """Calculates a composite score combining fuzzy matching and duration tie-breakers."""

        track_candidate = TrackNormalized.create(
            name=candidate.name,
            artists=[a.name for a in candidate.artists],
            duration_ms=candidate.duration_ms,
        )

        # 1. Base Text Match Scores
        track_score = fuzz.token_sort_ratio(track_target.name, track_candidate.name)
        artist_scores = [fuzz.WRatio(ta, ca) for ta in track_target.artists for ca in track_candidate.artists]
        best_artist_score = max(artist_scores) if artist_scores else 0.0

        if track_score < self.MATCH_THRESHOLD or best_artist_score < self.MATCH_THRESHOLD:
            return 0.0

        # Base composite: 60% track name weight, 40% artist name weight
        final_score = (track_score * 0.6) + (best_artist_score * 0.4)

        # 2. Duration Tie-Breaker
        if track_target.duration_ms and candidate.duration_ms:
            diff = abs(track_target.duration_ms - candidate.duration_ms)
            if diff <= 3000:
                final_score += 20.0  # Massive bonus for being within 3 seconds
            elif diff <= 10000:
                final_score += 5.0  # Small bonus for being within 10 seconds

        # 3. Provider Metadata Heuristics
        popularity = candidate.popularity or 0
        final_score += (popularity / 100.0) * 10.0

        album_type = candidate.album.album_type if candidate.album and candidate.album.album_type else ""
        if album_type == AlbumType.COMPILATION:
            final_score -= 15.0
        elif album_type == AlbumType.SINGLE:
            final_score -= 5.0
        elif album_type == AlbumType.EP:
            final_score -= 2.0

        return final_score
