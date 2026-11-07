import uuid
from unittest import mock

import pytest

from museflow.application.use_cases.playlist_view import get_playlist
from museflow.domain.exceptions import PlaylistNotFoundError

from tests.unit.factories.entities.user import UserFactory


class TestGetPlaylistUseCase:
    async def test__raises_when_not_found(
        self, mock_uow: mock.AsyncMock, mock_playlist_repository: mock.AsyncMock
    ) -> None:
        user = UserFactory.build()
        playlist_id = uuid.uuid4()
        mock_playlist_repository.get.return_value = None

        with pytest.raises(PlaylistNotFoundError):
            await get_playlist(
                user=user,
                playlist_id=playlist_id,
                uow=mock_uow,
            )
