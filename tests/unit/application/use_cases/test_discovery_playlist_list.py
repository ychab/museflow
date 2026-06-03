from unittest import mock

from museflow.application.use_cases.discovery_playlist_list import discovery_playlist_list

from tests.unit.factories.entities.discovery import DiscoveryPlaylistFactory
from tests.unit.factories.entities.user import UserFactory


class TestDiscoveryPlaylistListUseCase:
    async def test__nominal(self, mock_discovery_playlist_repository: mock.AsyncMock) -> None:
        user = UserFactory.build()
        playlists = DiscoveryPlaylistFactory.batch(2)
        mock_discovery_playlist_repository.list.return_value = playlists

        result = await discovery_playlist_list(
            user=user,
            discovery_playlist_repository=mock_discovery_playlist_repository,
        )

        assert result == playlists
        mock_discovery_playlist_repository.list.assert_awaited_once_with(user.id)

    async def test__empty(self, mock_discovery_playlist_repository: mock.AsyncMock) -> None:
        user = UserFactory.build()
        mock_discovery_playlist_repository.list.return_value = []

        result = await discovery_playlist_list(
            user=user,
            discovery_playlist_repository=mock_discovery_playlist_repository,
        )

        assert result == []

    async def test__delegates_user_id(self, mock_discovery_playlist_repository: mock.AsyncMock) -> None:
        user = UserFactory.build()
        mock_discovery_playlist_repository.list.return_value = []

        await discovery_playlist_list(
            user=user,
            discovery_playlist_repository=mock_discovery_playlist_repository,
        )

        mock_discovery_playlist_repository.list.assert_awaited_once_with(user.id)
