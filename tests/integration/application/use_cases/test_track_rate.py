from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.application.use_cases.track_rate import TrackRateUseCase
from museflow.domain.entities.user import User
from museflow.domain.enums import TrackSource
from museflow.infrastructure.adapters.database.models import Track as TrackModel

from tests.integration.factories.models.playlist import PlaylistModelFactory
from tests.integration.factories.models.track import TrackModelFactory


class TestTrackRateUseCase:
    async def test__find_history(self, uow: UnitOfWorkPort, user: User) -> None:
        less_played_db = await TrackModelFactory.create_async(
            user_id=user.id, source=TrackSource.HISTORY, score=None, played_count=3
        )
        most_played_db = await TrackModelFactory.create_async(
            user_id=user.id, source=TrackSource.HISTORY, score=None, played_count=10
        )
        await TrackModelFactory.create_async(user_id=user.id, source=TrackSource.HISTORY, score=7)
        await TrackModelFactory.create_async(user_id=user.id, source=TrackSource.HISTORY, score_skipped=True)
        await TrackModelFactory.create_async(user_id=user.id, source=TrackSource.DISCOVERY, score=None)
        await TrackModelFactory.create_async(source=TrackSource.HISTORY, score=None)
        use_case = TrackRateUseCase(user_id=user.id, provider=None, uow=uow)

        tracks = await use_case.find_history(limit=10, artist=None)

        assert [track.id for track in tracks] == [most_played_db.id, less_played_db.id]

    async def test__find_history__artist_and_limit(self, uow: UnitOfWorkPort, user: User) -> None:
        radiohead_db = await TrackModelFactory.create_async(
            user_id=user.id, source=TrackSource.HISTORY, score=None, artists=["Radiohead"], played_count=10
        )
        await TrackModelFactory.create_async(
            user_id=user.id, source=TrackSource.HISTORY, score=None, artists=["Radiohead"], played_count=1
        )
        await TrackModelFactory.create_async(
            user_id=user.id, source=TrackSource.HISTORY, score=None, artists=["Portishead"], played_count=20
        )
        use_case = TrackRateUseCase(user_id=user.id, provider=None, uow=uow)

        tracks = await use_case.find_history(limit=1, artist="radiohead")

        assert [track.id for track in tracks] == [radiohead_db.id]

    async def test__find_discovery(self, uow: UnitOfWorkPort, user: User) -> None:
        unrated_db = await TrackModelFactory.create_async(user_id=user.id, source=TrackSource.DISCOVERY, score=None)
        await TrackModelFactory.create_async(user_id=user.id, source=TrackSource.DISCOVERY, score=7)
        await TrackModelFactory.create_async(user_id=user.id, source=TrackSource.HISTORY, score=None)
        await TrackModelFactory.create_async(source=TrackSource.DISCOVERY, score=None)
        use_case = TrackRateUseCase(user_id=user.id, provider=None, uow=uow)

        tracks = await use_case.find_discovery(limit=10)

        assert [track.id for track in tracks] == [unrated_db.id]

    async def test__find_playlist(self, uow: UnitOfWorkPort, user: User) -> None:
        rated_db = await TrackModelFactory.create_async(user_id=user.id, score=7)
        unrated_db = await TrackModelFactory.create_async(user_id=user.id, score=None)
        playlist_db = await PlaylistModelFactory.create_async(user_id=user.id, track_ids=[rated_db.id, unrated_db.id])
        use_case = TrackRateUseCase(user_id=user.id, provider=None, uow=uow)

        tracks = await use_case.find_playlist(playlist_id=playlist_db.id)

        assert [track.id for track in tracks] == [rated_db.id, unrated_db.id]

    async def test__rate(self, uow: UnitOfWorkPort, async_session_db: AsyncSession, user: User) -> None:
        track_db = await TrackModelFactory.create_async(user_id=user.id, score=None)
        use_case = TrackRateUseCase(user_id=user.id, provider=None, uow=uow)

        await use_case.rate(track_id=track_db.id, score=8)

        score = (await async_session_db.execute(select(TrackModel.score).where(TrackModel.id == track_db.id))).scalar()
        assert score == 8

    async def test__skip(self, uow: UnitOfWorkPort, async_session_db: AsyncSession, user: User) -> None:
        track_db = await TrackModelFactory.create_async(user_id=user.id, score=None)
        use_case = TrackRateUseCase(user_id=user.id, provider=None, uow=uow)

        await use_case.skip(track_id=track_db.id)

        stmt = select(TrackModel.score_skipped).where(TrackModel.id == track_db.id)
        assert (await async_session_db.execute(stmt)).scalar() is True

    async def test__reset_scores(self, uow: UnitOfWorkPort, user: User) -> None:
        await TrackModelFactory.create_async(user_id=user.id, source=TrackSource.HISTORY, score=7)
        await TrackModelFactory.create_async(user_id=user.id, source=TrackSource.DISCOVERY, score=7)
        use_case = TrackRateUseCase(user_id=user.id, provider=None, uow=uow)

        count = await use_case.reset_scores(source=TrackSource.HISTORY)

        assert count == 1
        assert len(await use_case.find_history(limit=10, artist=None)) == 1
        assert await use_case.find_discovery(limit=10) == []

    async def test__blacklist(self, uow: UnitOfWorkPort, user: User) -> None:
        use_case = TrackRateUseCase(user_id=user.id, provider=None, uow=uow)

        await use_case.blacklist_track(name="Creep", artist_name="Radiohead")
        await use_case.blacklist_artist(artist_name="Portishead")

        async with uow:
            blacklist = await uow.blacklist.get_all(user_id=user.id)
        assert [(track.name, track.artist_name) for track in blacklist.tracks] == [("Creep", "Radiohead")]
        assert [artist.artist_name for artist in blacklist.artists] == ["Portishead"]
