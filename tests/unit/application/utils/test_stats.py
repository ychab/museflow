import pytest

from museflow.application.utils.stats import rank_stats
from museflow.domain.enums import RankingSortBy

from tests.unit.factories.value_objects.stats import ArtistStatsFactory


class TestRankStats:
    def test__unrated__ranked_by_volume(self) -> None:
        # Artist A: 5 unrated tracks. Artist B: 1 track rated 8. Volume first: A (quality ratio 1.0) outranks B.
        all_stats = [
            ArtistStatsFactory.build(artist="Artist A", track_count=5, plays_count=5, rated_count=0, rated_sum=0),
            ArtistStatsFactory.build(artist="Artist B", track_count=1, plays_count=1, rated_count=1, rated_sum=8),
        ]

        rankings = rank_stats(all_stats, global_mean=8.0, confidence=5, sort=RankingSortBy.OVERALL, limit=20)

        assert [r.stats.name for r in rankings] == ["Artist A", "Artist B"]
        assert rankings[0].rate_avg is None
        assert rankings[0].quality_score is None
        assert rankings[1].rate_avg == 8.0

    def test__quality__pulled_toward_global_mean(self) -> None:
        # Quality sort ignores volume: B's smoothed quality, pulled toward the mean, still beats A's.
        all_stats = [
            ArtistStatsFactory.build(artist="Artist A", track_count=10, rated_count=10, rated_sum=70),
            ArtistStatsFactory.build(artist="Artist B", track_count=1, rated_count=1, rated_sum=10),
        ]

        rankings = rank_stats(all_stats, global_mean=7.0, confidence=5, sort=RankingSortBy.QUALITY, limit=20)

        assert rankings[0].stats.name == "Artist B"
        assert rankings[0].quality_score == pytest.approx((5 * 7.0 + 10) / 6)

    @pytest.mark.parametrize(
        ("sort", "expected"),
        [
            pytest.param(RankingSortBy.OVERALL, ["Artist A", "Artist B"], id="overall_promotes_volume"),
            pytest.param(RankingSortBy.TRACK_COUNT, ["Artist A", "Artist B"], id="track_count"),
            pytest.param(RankingSortBy.PLAYS_COUNT, ["Artist B", "Artist A"], id="plays_count"),
            pytest.param(RankingSortBy.RATE_AVG, ["Artist B", "Artist A"], id="rate_avg"),
        ],
    )
    def test__sort(self, sort: RankingSortBy, expected: list[str]) -> None:
        # Artist A: 20 tracks at 7, played once each. Artist B: 1 track at 10, played 50 times.
        all_stats = [
            ArtistStatsFactory.build(artist="Artist A", track_count=20, plays_count=20, rated_count=20, rated_sum=140),
            ArtistStatsFactory.build(artist="Artist B", track_count=1, plays_count=50, rated_count=1, rated_sum=10),
        ]

        rankings = rank_stats(all_stats, global_mean=7.0, confidence=5, sort=sort, limit=20)

        assert [r.stats.name for r in rankings] == expected

    @pytest.mark.parametrize("sort", [RankingSortBy.RATE_AVG, RankingSortBy.QUALITY])
    def test__sort__unrated_at_bottom(self, sort: RankingSortBy) -> None:
        all_stats = [
            ArtistStatsFactory.build(artist="Artist A", track_count=10, rated_count=0, rated_sum=0),
            ArtistStatsFactory.build(artist="Artist B", track_count=1, rated_count=1, rated_sum=5),
        ]

        rankings = rank_stats(all_stats, global_mean=5.0, confidence=5, sort=sort, limit=20)

        assert [r.stats.name for r in rankings] == ["Artist B", "Artist A"]

    def test__tie__by_name(self) -> None:
        all_stats = [
            ArtistStatsFactory.build(artist="Zara", rated_count=1, rated_sum=8),
            ArtistStatsFactory.build(artist="Aaron", rated_count=1, rated_sum=8),
        ]

        rankings = rank_stats(all_stats, global_mean=8.0, confidence=5, sort=RankingSortBy.OVERALL, limit=20)

        assert [r.stats.name for r in rankings] == ["Aaron", "Zara"]

    def test__limit(self) -> None:
        all_stats = [ArtistStatsFactory.build(artist=f"Artist {i}") for i in range(5)]

        rankings = rank_stats(all_stats, global_mean=0.0, confidence=5, sort=RankingSortBy.OVERALL, limit=3)

        assert len(rankings) == 3
