import uuid
from unittest import mock

import pytest

from museflow.application.use_cases.taste_profile_delete import delete_taste_profile
from museflow.domain.exceptions import TasteProfileNotFoundError


class TestDeleteTasteProfileUseCase:
    async def test__nominal(self, mock_uow: mock.AsyncMock, mock_taste_profile_repository: mock.AsyncMock) -> None:
        user_id = uuid.uuid4()
        mock_taste_profile_repository.delete.return_value = True

        await delete_taste_profile(user_id=user_id, name="my-profile", uow=mock_uow)

        mock_taste_profile_repository.delete.assert_awaited_once_with(user_id=user_id, name="my-profile")

    async def test__not_found(self, mock_uow: mock.AsyncMock, mock_taste_profile_repository: mock.AsyncMock) -> None:
        mock_taste_profile_repository.delete.return_value = False

        with pytest.raises(TasteProfileNotFoundError):
            await delete_taste_profile(user_id=uuid.uuid4(), name="my-profile", uow=mock_uow)
