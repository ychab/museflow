import uuid
from unittest import mock

import pytest

from museflow.application.use_cases.remove_from_blacklist import RemoveFromBlacklistUseCase
from museflow.domain.exceptions import BlacklistItemNotFoundError


class TestRemoveFromBlacklistUseCase:
    async def test__remove__not_found(self, mock_blacklist_repository: mock.AsyncMock) -> None:
        item_id = uuid.uuid4()
        mock_blacklist_repository.remove.return_value = set()
        use_case = RemoveFromBlacklistUseCase(blacklist_repository=mock_blacklist_repository)

        with pytest.raises(BlacklistItemNotFoundError):
            await use_case.remove(user_id=uuid.uuid4(), item_ids=[item_id])

    async def test__remove__partial_not_found(self, mock_blacklist_repository: mock.AsyncMock) -> None:
        found_id = uuid.uuid4()
        missing_id = uuid.uuid4()
        mock_blacklist_repository.remove.return_value = {found_id}
        use_case = RemoveFromBlacklistUseCase(blacklist_repository=mock_blacklist_repository)

        with pytest.raises(BlacklistItemNotFoundError):
            await use_case.remove(user_id=uuid.uuid4(), item_ids=[found_id, missing_id])
