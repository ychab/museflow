from unittest import mock

from museflow.application.use_cases.taste_profile_import import import_taste_profile
from museflow.domain.entities.taste import TasteProfile
from museflow.domain.entities.user import User

from tests.unit.factories.entities.taste import TasteProfileFactory


class TestImportTasteProfileUseCase:
    async def test__new_id_generated_each_call(
        self,
        user: User,
        mock_uow: mock.AsyncMock,
        mock_taste_profile_repository: mock.AsyncMock,
    ) -> None:
        original_profile = TasteProfileFactory.build()
        mock_taste_profile_repository.upsert.side_effect = lambda profile: profile

        first = await import_taste_profile(user_id=user.id, taste_profile=original_profile, uow=mock_uow)
        second = await import_taste_profile(user_id=user.id, taste_profile=original_profile, uow=mock_uow)

        assert isinstance(first, TasteProfile)
        assert first.user_id == user.id
        assert first.id != second.id
        assert original_profile.id not in {first.id, second.id}
