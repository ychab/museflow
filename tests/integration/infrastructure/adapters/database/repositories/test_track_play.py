from datetime import UTC
from datetime import datetime

import pytest

from museflow.application.ports.repositories.track_play import TrackPlayRepository
from museflow.domain.entities.user import User
from museflow.infrastructure.adapters.database.models import Track as TrackModel

from tests.integration.factories.models.track import TrackModelFactory
from tests.integration.factories.models.track import TrackPlayModelFactory
from tests.integration.factories.models.user import UserModelFactory


class TestTrackPlaySQLRepository:
    @pytest.fixture
    async def tracks_db(self, user: User) -> dict[str, TrackModel]:
        """Plays of 2020 then 2022: `replayed` in both years, `early` and `rated` in 2020, `late` in 2022, `silent` never.

        Sorted, the 8 plays split into 2 periods of 4: replayed ×2, early, rated | replayed ×2, late ×2.
        """
        tracks_db = {
            name: await TrackModelFactory.create_async(user_id=user.id, score=score)
            for name, score in [("replayed", None), ("early", None), ("rated", 9), ("late", None), ("silent", None)]
        }
        plays = [
            ("replayed", datetime(2020, 1, 1, tzinfo=UTC)),
            ("replayed", datetime(2020, 1, 2, tzinfo=UTC)),
            ("early", datetime(2020, 1, 3, tzinfo=UTC)),
            ("rated", datetime(2020, 1, 4, tzinfo=UTC)),
            ("replayed", datetime(2022, 1, 1, tzinfo=UTC)),
            ("replayed", datetime(2022, 1, 2, tzinfo=UTC)),
            ("late", datetime(2022, 1, 3, tzinfo=UTC)),
            ("late", datetime(2022, 1, 4, tzinfo=UTC)),
        ]
        for name, played_at in plays:
            await TrackPlayModelFactory.create_async(track_id=tracks_db[name].id, played_at=played_at)
        # Another user's plays stay out
        other_user_db = await UserModelFactory.create_async()
        await TrackModelFactory.create_async(user_id=other_user_db.id, played_count=5)
        return tracks_db

    async def test__count_played_tracks(
        self,
        user: User,
        tracks_db: dict[str, TrackModel],
        track_play_repository: TrackPlayRepository,
    ) -> None:
        assert await track_play_repository.count_played_tracks(user_id=user.id) == 4
        assert await track_play_repository.count_played_tracks(user_id=user.id, min_score=0) == 1

    async def test__get_periods__nominal(
        self,
        user: User,
        tracks_db: dict[str, TrackModel],
        track_play_repository: TrackPlayRepository,
    ) -> None:
        periods = await track_play_repository.get_periods(user_id=user.id, periods=2, tracks_per_period=2)

        names = {track_db.id: name for name, track_db in tracks_db.items()}
        assert [
            (period.start, period.end, period.plays, [(names[pt.track.id], pt.plays) for pt in period.tracks])
            for period in periods
        ] == [
            # Most played first, then the cut: `early` and `rated` tie, only one fits (the lower id)
            (
                datetime(2020, 1, 1, tzinfo=UTC),
                datetime(2020, 1, 4, tzinfo=UTC),
                4,
                [("replayed", 2), (names[min(tracks_db["early"].id, tracks_db["rated"].id)], 1)],
            ),
            (datetime(2022, 1, 1, tzinfo=UTC), datetime(2022, 1, 4, tzinfo=UTC), 4, [("replayed", 2), ("late", 2)]),
        ]
        # The tracks carry their play data over the whole history, not the period's
        replayed = periods[0].tracks[0].track
        assert (replayed.played_count, replayed.played_at_first, replayed.played_at_last) == (
            4,
            datetime(2020, 1, 1, tzinfo=UTC),
            datetime(2022, 1, 2, tzinfo=UTC),
        )

    async def test__get_periods__min_score(
        self,
        user: User,
        tracks_db: dict[str, TrackModel],
        track_play_repository: TrackPlayRepository,
    ) -> None:
        periods = await track_play_repository.get_periods(user_id=user.id, periods=2, tracks_per_period=2, min_score=0)

        # A single rated play: fewer periods than asked
        assert [(period.plays, [pt.track.id for pt in period.tracks]) for period in periods] == [
            (1, [tracks_db["rated"].id])
        ]
