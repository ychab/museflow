from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.application.use_cases.taste_profile_view import get_taste_profile
from museflow.domain.entities.user import User

from tests.integration.factories.models.taste import TasteProfileModelFactory


class TestGetTasteProfileUseCase:
    async def test__nominal(self, uow: UnitOfWorkPort, user: User) -> None:
        taste_profile_db = await TasteProfileModelFactory.create_async(user_id=user.id, name="my-profile")

        result = await get_taste_profile(user_id=user.id, name="my-profile", uow=uow)

        assert result.id == taste_profile_db.id
