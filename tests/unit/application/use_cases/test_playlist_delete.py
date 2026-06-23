import uuid
from unittest import mock

import pytest

from museflow.application.use_cases.playlist_delete import playlist_delete
from museflow.domain.exceptions import PlaylistNotFoundError
from museflow.domain.types import MusicProvider
from museflow.domain.types import PlaylistType

from tests.unit.factories.entities.user import UserFactory


class TestPlaylistDeleteUseCase:
    async def test__no_playlist_id_and_no_purge__raises_not_found(
        self,
        mock_playlist_repository: mock.AsyncMock,
    ) -> None:
        user = UserFactory.build()

        with pytest.raises(PlaylistNotFoundError):
            await playlist_delete(user=user, playlist_repository=mock_playlist_repository)

        mock_playlist_repository.delete.assert_not_awaited()

    async def test__single_delete__not_found(self, mock_playlist_repository: mock.AsyncMock) -> None:
        user = UserFactory.build()
        mock_playlist_repository.delete.return_value = False

        with pytest.raises(PlaylistNotFoundError):
            await playlist_delete(
                user=user,
                playlist_repository=mock_playlist_repository,
                playlist_id=uuid.uuid4(),
            )

    async def test__purge__calls_repository_with_filters(self, mock_playlist_repository: mock.AsyncMock) -> None:
        user = UserFactory.build()
        mock_playlist_repository.purge.return_value = 5

        count = await playlist_delete(
            user=user,
            playlist_repository=mock_playlist_repository,
            purge=True,
            type=PlaylistType.DISCOVERY,
            provider=MusicProvider.SPOTIFY,
        )

        assert count == 5
        mock_playlist_repository.purge.assert_called_once_with(
            user_id=user.id,
            type=PlaylistType.DISCOVERY,
            provider=MusicProvider.SPOTIFY,
        )
