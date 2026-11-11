import math


def compute_quality(rate_avg: float | None, rated_count: int, global_mean: float, confidence: int) -> float:
    """Bayesian average: the fewer the ratings, the closer to the global mean; the mean itself without ratings."""
    if rate_avg is None:
        return global_mean
    return (confidence * global_mean + rated_count * rate_avg) / (confidence + rated_count)


def compute_overall(track_count: int, plays_count: int, quality: float, global_mean: float) -> float:
    """Breadth x depth x quality, the quality as a ratio to the global mean (neutral when nothing is rated)."""
    quality_ratio = quality / global_mean if global_mean > 0 else 1.0
    return math.log(1 + track_count) * math.log(1 + plays_count) * quality_ratio
