from museflow.domain.types import TrackOrderBy


class TestTrackOrderBy:
    def test__nullable__played_at(self) -> None:
        assert TrackOrderBy.PLAYED_AT.nullable is True

    def test__nullable__non_nullable(self) -> None:
        for col in (TrackOrderBy.CREATED_AT, TrackOrderBy.UPDATED_AT, TrackOrderBy.RANDOM):
            assert col.nullable is False
