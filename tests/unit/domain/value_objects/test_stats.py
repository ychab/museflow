from museflow.domain.value_objects.stats import LibraryStats


class TestLibraryStats:
    def test__rate_avg(self) -> None:
        library_stats = LibraryStats(track_count=3, rated_count=2, rated_sum=15, unenriched_count=0)

        assert library_stats.rate_avg == 7.5

    def test__rate_avg__nothing_rated(self) -> None:
        library_stats = LibraryStats(track_count=3, rated_count=0, rated_sum=0, unenriched_count=0)

        assert library_stats.rate_avg == 0.0
