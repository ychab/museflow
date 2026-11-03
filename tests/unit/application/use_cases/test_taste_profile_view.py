from unittest import mock

import pytest

from museflow.application.use_cases.taste_profile_view import view_taste_profile
from museflow.domain.exceptions import TasteProfileNotFoundException

from tests.unit.factories.entities.taste import TasteProfileFactory


class TestViewTasteProfileUseCase:
    async def test__not_found(self, mock_uow: mock.AsyncMock, mock_taste_profile_repository: mock.AsyncMock) -> None:
        mock_taste_profile_repository.get.return_value = None

        with pytest.raises(TasteProfileNotFoundException):
            await view_taste_profile(user_id=TasteProfileFactory.build().user_id, name="my-profile", uow=mock_uow)
