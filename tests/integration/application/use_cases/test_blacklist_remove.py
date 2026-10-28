from museflow.application.ports.repositories.blacklist import BlacklistRepository
from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.application.use_cases.blacklist_remove import RemoveFromBlacklistUseCase
from museflow.domain.entities.user import User

from tests.integration.factories.models.blacklist import BlacklistedArtistModelFactory
from tests.integration.factories.models.blacklist import BlacklistedTrackModelFactory


class TestRemoveFromBlacklistUseCase:
    async def test__remove__artist(
        self,
        uow: UnitOfWorkPort,
        user: User,
        blacklist_repository: BlacklistRepository,
    ) -> None:
        artist_db = await BlacklistedArtistModelFactory.create_async(user_id=user.id)
        use_case = RemoveFromBlacklistUseCase(uow=uow)

        await use_case.remove(user_id=user.id, item_ids=[artist_db.id])

        result = await blacklist_repository.get_all(user_id=user.id)
        assert result.is_empty

    async def test__remove__track(
        self,
        uow: UnitOfWorkPort,
        user: User,
        blacklist_repository: BlacklistRepository,
    ) -> None:
        track_db = await BlacklistedTrackModelFactory.create_async(user_id=user.id)
        use_case = RemoveFromBlacklistUseCase(uow=uow)

        await use_case.remove(user_id=user.id, item_ids=[track_db.id])

        result = await blacklist_repository.get_all(user_id=user.id)
        assert result.is_empty

    async def test__remove__multiple(
        self,
        uow: UnitOfWorkPort,
        user: User,
        blacklist_repository: BlacklistRepository,
    ) -> None:
        artist_db = await BlacklistedArtistModelFactory.create_async(user_id=user.id)
        track_db = await BlacklistedTrackModelFactory.create_async(user_id=user.id)
        use_case = RemoveFromBlacklistUseCase(uow=uow)

        await use_case.remove(user_id=user.id, item_ids=[artist_db.id, track_db.id])

        result = await blacklist_repository.get_all(user_id=user.id)
        assert result.is_empty

    async def test__purge(
        self,
        uow: UnitOfWorkPort,
        user: User,
        blacklist_repository: BlacklistRepository,
    ) -> None:
        await BlacklistedArtistModelFactory.create_async(user_id=user.id)
        await BlacklistedTrackModelFactory.create_async(user_id=user.id)
        use_case = RemoveFromBlacklistUseCase(uow=uow)

        count = await use_case.purge(user_id=user.id)

        assert count == 2
        result = await blacklist_repository.get_all(user_id=user.id)
        assert result.is_empty
