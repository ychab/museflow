from museflow.application.ports.repositories.taste import TasteProfileRepository
from museflow.application.use_cases.list_taste_profiles import list_taste_profiles
from museflow.domain.entities.user import User

from tests.integration.factories.models.taste import TasteProfileModelFactory


class TestListTasteProfilesUseCase:
    async def test__nominal(
        self,
        user: User,
        taste_profile_repository: TasteProfileRepository,
    ) -> None:
        profile_a = await TasteProfileModelFactory.create_async(user_id=user.id, name="alpha")
        profile_b = await TasteProfileModelFactory.create_async(user_id=user.id, name="beta")

        result = await list_taste_profiles(user_id=user.id, taste_profile_repository=taste_profile_repository)

        assert len(result) == 2
        result_ids = {p.id for p in result}
        assert profile_a.id in result_ids
        assert profile_b.id in result_ids

    async def test__empty(
        self,
        user: User,
        taste_profile_repository: TasteProfileRepository,
    ) -> None:
        result = await list_taste_profiles(user_id=user.id, taste_profile_repository=taste_profile_repository)

        assert result == []
