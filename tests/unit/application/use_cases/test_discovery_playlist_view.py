import uuid
from unittest import mock

import pytest

from museflow.application.use_cases.discovery_playlist_view import discovery_playlist_view
from museflow.domain.exceptions import DiscoveryPlaylistNotFoundError

from tests.unit.factories.entities.discovery import DiscoveryPlaylistFactory
from tests.unit.factories.entities.user import UserFactory


class TestDiscoveryPlaylistViewUseCase:
    async def test__nominal(self, mock_discovery_playlist_repository: mock.AsyncMock) -> None:
        user = UserFactory.build()
        playlist = DiscoveryPlaylistFactory.build()
        mock_discovery_playlist_repository.get.return_value = playlist

        result = await discovery_playlist_view(
            user=user,
            playlist_id=playlist.id,
            discovery_playlist_repository=mock_discovery_playlist_repository,
        )

        assert result == playlist
        mock_discovery_playlist_repository.get.assert_awaited_once_with(user.id, playlist.id)

    async def test__raises_when_not_found(self, mock_discovery_playlist_repository: mock.AsyncMock) -> None:
        user = UserFactory.build()
        playlist_id = uuid.uuid4()
        mock_discovery_playlist_repository.get.return_value = None

        with pytest.raises(DiscoveryPlaylistNotFoundError):
            await discovery_playlist_view(
                user=user,
                playlist_id=playlist_id,
                discovery_playlist_repository=mock_discovery_playlist_repository,
            )
