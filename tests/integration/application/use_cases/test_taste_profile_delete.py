import pytest

from museflow.application.ports.repositories.taste import TasteProfileRepository
from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.application.use_cases.taste_profile_delete import delete_taste_profile
from museflow.domain.entities.user import User
from museflow.domain.exceptions import TasteProfileNotFoundException

from tests.integration.factories.models.taste import TasteProfileModelFactory


class TestDeleteTasteProfileUseCase:
    async def test__nominal(
        self,
        uow: UnitOfWorkPort,
        user: User,
        taste_profile_repository: TasteProfileRepository,
    ) -> None:
        await TasteProfileModelFactory.create_async(user_id=user.id, name="my-profile")

        await delete_taste_profile(user_id=user.id, name="my-profile", uow=uow)

        assert await taste_profile_repository.get(user_id=user.id, name="my-profile") is None

    async def test__not_found(self, uow: UnitOfWorkPort, user: User) -> None:
        with pytest.raises(TasteProfileNotFoundException):
            await delete_taste_profile(user_id=user.id, name="my-profile", uow=uow)
