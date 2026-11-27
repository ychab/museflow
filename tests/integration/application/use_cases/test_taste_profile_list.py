from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.application.use_cases.taste_profile_list import get_taste_profiles
from museflow.domain.entities.user import User

from tests.integration.factories.models.taste import TasteProfileModelFactory


class TestGetTasteProfilesUseCase:
    async def test__nominal(
        self,
        uow: UnitOfWorkPort,
        user: User,
    ) -> None:
        profile_a = await TasteProfileModelFactory.create_async(user_id=user.id, name="alpha")
        profile_b = await TasteProfileModelFactory.create_async(user_id=user.id, name="beta")

        page = await get_taste_profiles(user_id=user.id, uow=uow)

        assert {profile.id for profile in page.items} == {profile_a.id, profile_b.id}
        assert (page.total, page.limit, page.offset) == (2, None, 0)

    async def test__paged(self, uow: UnitOfWorkPort, user: User) -> None:
        for _ in range(3):
            await TasteProfileModelFactory.create_async(user_id=user.id)

        page = await get_taste_profiles(user_id=user.id, uow=uow, limit=2, offset=2)

        assert len(page.items) == 1
        assert (page.total, page.limit, page.offset) == (3, 2, 2)

    async def test__empty(
        self,
        uow: UnitOfWorkPort,
        user: User,
    ) -> None:
        page = await get_taste_profiles(user_id=user.id, uow=uow)

        assert page.items == []
        assert page.total == 0
