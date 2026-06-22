import uuid
from unittest import mock

import pytest

from museflow.application.use_cases.playlist_view import playlist_view
from museflow.domain.exceptions import PlaylistNotFoundError

from tests.unit.factories.entities.user import UserFactory


class TestPlaylistViewUseCase:
    async def test__raises_when_not_found(self, mock_playlist_repository: mock.AsyncMock) -> None:
        user = UserFactory.build()
        playlist_id = uuid.uuid4()
        mock_playlist_repository.get.return_value = None

        with pytest.raises(PlaylistNotFoundError):
            await playlist_view(
                user=user,
                playlist_id=playlist_id,
                playlist_repository=mock_playlist_repository,
            )
