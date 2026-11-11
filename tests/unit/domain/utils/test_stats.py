import math

import pytest

from museflow.domain.utils.stats import compute_overall
from museflow.domain.utils.stats import compute_quality


class TestComputeQuality:
    def test__pulled_toward_global_mean(self) -> None:
        # (5 * 7 + 1 * 10) / (5 + 1)
        assert compute_quality(rate_avg=10.0, rated_count=1, global_mean=7.0, confidence=5) == pytest.approx(7.5)

    def test__more_ratings__closer_to_own_average(self) -> None:
        few = compute_quality(rate_avg=10.0, rated_count=1, global_mean=7.0, confidence=5)
        many = compute_quality(rate_avg=10.0, rated_count=50, global_mean=7.0, confidence=5)

        assert few < many < 10.0

    def test__unrated__global_mean(self) -> None:
        assert compute_quality(rate_avg=None, rated_count=0, global_mean=7.0, confidence=5) == 7.0


class TestComputeOverall:
    def test__quality_as_ratio_to_global_mean(self) -> None:
        overall = compute_overall(track_count=2, plays_count=3, quality=8.0, global_mean=4.0)

        assert overall == pytest.approx(math.log(3) * math.log(4) * 2.0)

    def test__no_global_mean__neutral_ratio(self) -> None:
        overall = compute_overall(track_count=1, plays_count=1, quality=0.0, global_mean=0.0)

        assert overall == pytest.approx(math.log(2) ** 2)
