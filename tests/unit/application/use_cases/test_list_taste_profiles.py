from unittest import mock

from museflow.application.use_cases.list_taste_profiles import list_taste_profiles

from tests.unit.factories.entities.taste import TasteProfileFactory


class TestListTasteProfilesUseCase:
    async def test__nominal(self, mock_taste_profile_repository: mock.AsyncMock) -> None:
        profiles = TasteProfileFactory.batch(2)
        mock_taste_profile_repository.list.return_value = profiles

        result = await list_taste_profiles(
            user_id=profiles[0].user_id,
            taste_profile_repository=mock_taste_profile_repository,
        )

        assert result == profiles

    async def test__empty(self, mock_taste_profile_repository: mock.AsyncMock) -> None:
        mock_taste_profile_repository.list.return_value = []

        result = await list_taste_profiles(
            user_id=TasteProfileFactory.build().user_id,
            taste_profile_repository=mock_taste_profile_repository,
        )

        assert result == []
