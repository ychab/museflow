from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.application.use_cases.taste_profile_list import list_taste_profiles
from museflow.domain.entities.user import User

from tests.integration.factories.models.taste import TasteProfileModelFactory


class TestListTasteProfilesUseCase:
    async def test__nominal(
        self,
        uow: UnitOfWorkPort,
        user: User,
    ) -> None:
        profile_a = await TasteProfileModelFactory.create_async(user_id=user.id, name="alpha")
        profile_b = await TasteProfileModelFactory.create_async(user_id=user.id, name="beta")

        result = await list_taste_profiles(user_id=user.id, uow=uow)

        assert len(result) == 2
        result_ids = {p.id for p in result}
        assert profile_a.id in result_ids
        assert profile_b.id in result_ids

    async def test__empty(
        self,
        uow: UnitOfWorkPort,
        user: User,
    ) -> None:
        result = await list_taste_profiles(user_id=user.id, uow=uow)

        assert result == []
