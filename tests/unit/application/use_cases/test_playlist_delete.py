import uuid
from unittest import mock

import pytest

from museflow.application.use_cases.playlist_delete import PlaylistDeleteUseCase
from museflow.domain.enums import MusicProvider
from museflow.domain.enums import PlaylistType
from museflow.domain.exceptions import PlaylistNotFoundError

from tests.unit.factories.entities.playlist import PlaylistFactory
from tests.unit.factories.entities.user import UserFactory


class TestPlaylistDeleteUseCase:
    @pytest.fixture
    def use_case(self, mock_playlist_repository: mock.AsyncMock) -> PlaylistDeleteUseCase:
        return PlaylistDeleteUseCase(playlist_repository=mock_playlist_repository)

    @pytest.fixture
    def use_case_with_remote(
        self, mock_playlist_repository: mock.AsyncMock, mock_provider_library: mock.AsyncMock
    ) -> PlaylistDeleteUseCase:
        return PlaylistDeleteUseCase(
            playlist_repository=mock_playlist_repository,
            provider_library=mock_provider_library,
        )

    async def test__delete__nominal(
        self, use_case: PlaylistDeleteUseCase, mock_playlist_repository: mock.AsyncMock
    ) -> None:
        user = UserFactory.build()
        playlist_id = uuid.uuid4()
        mock_playlist_repository.delete.return_value = True

        await use_case.delete(user=user, playlist_id=playlist_id)
        mock_playlist_repository.delete.assert_awaited_once_with(user_id=user.id, playlist_id=playlist_id)

    async def test__delete__not_found(
        self, use_case: PlaylistDeleteUseCase, mock_playlist_repository: mock.AsyncMock
    ) -> None:
        user = UserFactory.build()
        mock_playlist_repository.delete.return_value = False

        with pytest.raises(PlaylistNotFoundError):
            await use_case.delete(user=user, playlist_id=uuid.uuid4())

    async def test__delete__include_remote__requires_provider_library(self, use_case: PlaylistDeleteUseCase) -> None:
        user = UserFactory.build()

        with pytest.raises(ValueError, match="provider_library is required"):
            await use_case.delete(user=user, playlist_id=uuid.uuid4(), include_remote=True)

    async def test__delete__include_remote__nominal(
        self,
        use_case_with_remote: PlaylistDeleteUseCase,
        mock_playlist_repository: mock.AsyncMock,
        mock_provider_library: mock.AsyncMock,
    ) -> None:
        user = UserFactory.build()
        playlist = PlaylistFactory.build(user_id=user.id)
        mock_playlist_repository.get.return_value = playlist
        mock_playlist_repository.delete.return_value = True

        await use_case_with_remote.delete(user=user, playlist_id=playlist.id, include_remote=True)
        mock_provider_library.delete_playlist.assert_awaited_once_with(playlist.provider_id)
        mock_playlist_repository.delete.assert_awaited_once_with(user_id=user.id, playlist_id=playlist.id)

    async def test__delete__include_remote__not_found(
        self,
        use_case_with_remote: PlaylistDeleteUseCase,
        mock_playlist_repository: mock.AsyncMock,
        mock_provider_library: mock.AsyncMock,
    ) -> None:
        user = UserFactory.build()
        mock_playlist_repository.get.return_value = None

        with pytest.raises(PlaylistNotFoundError):
            await use_case_with_remote.delete(user=user, playlist_id=uuid.uuid4(), include_remote=True)

        mock_provider_library.delete_playlist.assert_not_awaited()
        mock_playlist_repository.delete.assert_not_awaited()

    async def test__delete__include_remote__local_delete_returns_false(
        self,
        use_case_with_remote: PlaylistDeleteUseCase,
        mock_playlist_repository: mock.AsyncMock,
        mock_provider_library: mock.AsyncMock,
    ) -> None:
        user = UserFactory.build()
        playlist = PlaylistFactory.build(user_id=user.id)
        mock_playlist_repository.get.return_value = playlist
        mock_playlist_repository.delete.return_value = False

        with pytest.raises(PlaylistNotFoundError):
            await use_case_with_remote.delete(user=user, playlist_id=playlist.id, include_remote=True)

        mock_provider_library.delete_playlist.assert_awaited_once_with(playlist.provider_id)

    async def test__delete__include_remote__remote_error_propagates(
        self,
        use_case_with_remote: PlaylistDeleteUseCase,
        mock_playlist_repository: mock.AsyncMock,
        mock_provider_library: mock.AsyncMock,
    ) -> None:
        user = UserFactory.build()
        playlist = PlaylistFactory.build(user_id=user.id)
        mock_playlist_repository.get.return_value = playlist
        mock_provider_library.delete_playlist.side_effect = RuntimeError("Spotify down")

        with pytest.raises(RuntimeError, match="Spotify down"):
            await use_case_with_remote.delete(user=user, playlist_id=playlist.id, include_remote=True)

        mock_playlist_repository.delete.assert_not_awaited()

    async def test__purge__nominal(
        self, use_case: PlaylistDeleteUseCase, mock_playlist_repository: mock.AsyncMock
    ) -> None:
        user = UserFactory.build()
        mock_playlist_repository.purge.return_value = 5

        count = await use_case.purge(user=user, type=PlaylistType.DISCOVERY, provider=MusicProvider.SPOTIFY)

        assert count == 5
        mock_playlist_repository.purge.assert_called_once_with(
            user_id=user.id,
            type=PlaylistType.DISCOVERY,
            provider=MusicProvider.SPOTIFY,
        )

    async def test__purge__include_remote__requires_provider_library(self, use_case: PlaylistDeleteUseCase) -> None:
        user = UserFactory.build()

        with pytest.raises(ValueError, match="provider_library is required"):
            await use_case.purge(user=user, include_remote=True)

    async def test__purge__include_remote__nominal(
        self,
        use_case_with_remote: PlaylistDeleteUseCase,
        mock_playlist_repository: mock.AsyncMock,
        mock_provider_library: mock.AsyncMock,
    ) -> None:
        user = UserFactory.build()
        playlists = PlaylistFactory.batch(2, user_id=user.id)
        mock_playlist_repository.list.return_value = playlists
        mock_playlist_repository.delete.return_value = True

        count = await use_case_with_remote.purge(user=user, include_remote=True)

        assert count == 2
        assert mock_provider_library.delete_playlist.await_count == 2
        assert mock_playlist_repository.delete.await_count == 2

    async def test__purge__include_remote__remote_failure_skipped(
        self,
        use_case_with_remote: PlaylistDeleteUseCase,
        mock_playlist_repository: mock.AsyncMock,
        mock_provider_library: mock.AsyncMock,
    ) -> None:
        user = UserFactory.build()
        playlists = PlaylistFactory.batch(2, user_id=user.id)
        mock_playlist_repository.list.return_value = playlists
        mock_provider_library.delete_playlist.side_effect = [RuntimeError("network error"), None]
        mock_playlist_repository.delete.return_value = True

        count = await use_case_with_remote.purge(user=user, include_remote=True)

        assert count == 1
        mock_playlist_repository.delete.assert_awaited_once_with(user_id=user.id, playlist_id=playlists[1].id)

    async def test__purge__include_remote__filters_applied(
        self,
        use_case_with_remote: PlaylistDeleteUseCase,
        mock_playlist_repository: mock.AsyncMock,
        mock_provider_library: mock.AsyncMock,
    ) -> None:
        user = UserFactory.build()
        discovery = PlaylistFactory.build(user_id=user.id, type=PlaylistType.DISCOVERY)
        history = PlaylistFactory.build(user_id=user.id, type=PlaylistType.HISTORY)
        mock_playlist_repository.list.return_value = [discovery, history]
        mock_playlist_repository.delete.return_value = True

        count = await use_case_with_remote.purge(user=user, type=PlaylistType.DISCOVERY, include_remote=True)

        assert count == 1
        mock_provider_library.delete_playlist.assert_awaited_once_with(discovery.provider_id)
        mock_playlist_repository.delete.assert_awaited_once_with(user_id=user.id, playlist_id=discovery.id)
