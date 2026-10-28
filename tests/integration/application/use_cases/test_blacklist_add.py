from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.application.use_cases.blacklist_add import AddToBlacklistUseCase
from museflow.domain.entities.user import User
from museflow.infrastructure.adapters.database.models.blacklist import BlacklistedArtist as BlacklistedArtistModel
from museflow.infrastructure.adapters.database.models.blacklist import BlacklistedTrack as BlacklistedTrackModel


class TestAddToBlacklistUseCase:
    async def test__add_artist__nominal(
        self,
        uow: UnitOfWorkPort,
        async_session_db: AsyncSession,
        user: User,
    ) -> None:
        use_case = AddToBlacklistUseCase(uow=uow)

        entity = await use_case.add_artist(user_id=user.id, artist_name="Taylor Swift")

        assert entity.artist_name == "Taylor Swift"
        assert entity.user_id == user.id

        count = (
            await async_session_db.execute(
                select(func.count()).select_from(BlacklistedArtistModel).where(BlacklistedArtistModel.id == entity.id)
            )
        ).scalar()
        assert count == 1

    async def test__add_track__nominal(
        self,
        uow: UnitOfWorkPort,
        async_session_db: AsyncSession,
        user: User,
    ) -> None:
        use_case = AddToBlacklistUseCase(uow=uow)

        entity = await use_case.add_track(user_id=user.id, name="Shake It Off", artist_name="Taylor Swift")

        assert entity.name == "Shake It Off"
        assert entity.artist_name == "Taylor Swift"
        assert entity.user_id == user.id

        count = (
            await async_session_db.execute(
                select(func.count()).select_from(BlacklistedTrackModel).where(BlacklistedTrackModel.id == entity.id)
            )
        ).scalar()
        assert count == 1
