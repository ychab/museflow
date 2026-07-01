from museflow.domain.enums import TrackOrderBy


class TestTrackOrderBy:
    def test__nullable__played_at_last(self) -> None:
        assert TrackOrderBy.PLAYED_AT_LAST.nullable is True

    def test__nullable__played_at_first(self) -> None:
        assert TrackOrderBy.PLAYED_AT_FIRST.nullable is True

    def test__nullable__non_nullable(self) -> None:
        for col in (TrackOrderBy.CREATED_AT, TrackOrderBy.UPDATED_AT, TrackOrderBy.RANDOM, TrackOrderBy.PLAYED_COUNT):
            assert col.nullable is False
