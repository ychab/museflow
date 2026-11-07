import uuid
from unittest import mock

import pytest

from museflow.application.ports.providers.library import ProviderLibraryPort
from museflow.application.use_cases.playlist_delete import DeletePlaylistUseCase
from museflow.domain.entities.user import User
from museflow.domain.enums import MusicProvider
from museflow.domain.enums import PlaylistType
from museflow.domain.exceptions import PlaylistNotFoundError

from tests.unit.factories.entities.playlist import PlaylistFactory
from tests.unit.factories.entities.user import UserFactory


class TestDeletePlaylistUseCase:
    @pytest.fixture
    def user(self) -> User:
        return UserFactory.build()

    @pytest.fixture
    def use_case(self, user: User, mock_uow: mock.AsyncMock) -> DeletePlaylistUseCase:
        return DeletePlaylistUseCase(user_id=user.id, uow=mock_uow)

    @pytest.fixture
    def provider_libraries(self, mock_provider_library: mock.AsyncMock) -> dict[MusicProvider, ProviderLibraryPort]:
        return {MusicProvider.SPOTIFY: mock_provider_library}

    async def test__find__not_found(
        self,
        use_case: DeletePlaylistUseCase,
        mock_playlist_repository: mock.AsyncMock,
    ) -> None:
        mock_playlist_repository.get.return_value = None

        with pytest.raises(PlaylistNotFoundError):
            await use_case.find(playlist_id=uuid.uuid4())

    async def test__find_matching__filters_applied(
        self,
        use_case: DeletePlaylistUseCase,
        user: User,
        mock_playlist_repository: mock.AsyncMock,
    ) -> None:
        discovery = PlaylistFactory.build(user_id=user.id, type=PlaylistType.DISCOVERY)
        history = PlaylistFactory.build(user_id=user.id, type=PlaylistType.HISTORY)
        other_provider = PlaylistFactory.build(user_id=user.id, type=PlaylistType.DISCOVERY, provider="foo")
        mock_playlist_repository.get_list.return_value = [discovery, history, other_provider]

        playlists = await use_case.find_matching(type=PlaylistType.DISCOVERY, provider=MusicProvider.SPOTIFY)

        assert playlists == [discovery]

    async def test__delete__not_found(
        self,
        use_case: DeletePlaylistUseCase,
        mock_playlist_repository: mock.AsyncMock,
    ) -> None:
        mock_playlist_repository.delete.return_value = False

        with pytest.raises(PlaylistNotFoundError):
            await use_case.delete(playlist_id=uuid.uuid4())

    async def test__delete_remote__own_provider_library(
        self,
        use_case: DeletePlaylistUseCase,
        user: User,
        mock_playlist_repository: mock.AsyncMock,
    ) -> None:
        spotify_library = mock.AsyncMock(spec=ProviderLibraryPort)
        other_library = mock.AsyncMock(spec=ProviderLibraryPort)
        playlist = PlaylistFactory.build(user_id=user.id, provider="foo")
        mock_playlist_repository.delete.return_value = True

        await use_case.delete_remote(
            playlist=playlist,
            provider_libraries={MusicProvider.SPOTIFY: spotify_library, "foo": other_library},  # type: ignore[dict-item]
        )

        other_library.delete_playlist.assert_awaited_once_with(playlist.provider_id)
        spotify_library.delete_playlist.assert_not_awaited()
        mock_playlist_repository.delete.assert_awaited_once_with(user_id=user.id, playlist_id=playlist.id)

    async def test__delete_remote__local_delete_returns_false(
        self,
        use_case: DeletePlaylistUseCase,
        user: User,
        mock_playlist_repository: mock.AsyncMock,
        mock_provider_library: mock.AsyncMock,
        provider_libraries: dict[MusicProvider, ProviderLibraryPort],
    ) -> None:
        playlist = PlaylistFactory.build(user_id=user.id)
        mock_playlist_repository.delete.return_value = False

        with pytest.raises(PlaylistNotFoundError):
            await use_case.delete_remote(playlist=playlist, provider_libraries=provider_libraries)

        mock_provider_library.delete_playlist.assert_awaited_once_with(playlist.provider_id)

    async def test__delete_remote__remote_error_propagates(
        self,
        use_case: DeletePlaylistUseCase,
        user: User,
        mock_playlist_repository: mock.AsyncMock,
        mock_provider_library: mock.AsyncMock,
        provider_libraries: dict[MusicProvider, ProviderLibraryPort],
    ) -> None:
        playlist = PlaylistFactory.build(user_id=user.id)
        mock_provider_library.delete_playlist.side_effect = RuntimeError("Provider down")

        with pytest.raises(RuntimeError, match="Provider down"):
            await use_case.delete_remote(playlist=playlist, provider_libraries=provider_libraries)

        mock_playlist_repository.delete.assert_not_awaited()

    async def test__purge_remote__mixed_providers(
        self,
        use_case: DeletePlaylistUseCase,
        user: User,
        mock_playlist_repository: mock.AsyncMock,
    ) -> None:
        spotify_library = mock.AsyncMock(spec=ProviderLibraryPort)
        other_library = mock.AsyncMock(spec=ProviderLibraryPort)
        spotify_playlist = PlaylistFactory.build(user_id=user.id, provider=MusicProvider.SPOTIFY)
        other_playlist = PlaylistFactory.build(user_id=user.id, provider="foo")

        count = await use_case.purge_remote(
            playlists=[spotify_playlist, other_playlist],
            provider_libraries={MusicProvider.SPOTIFY: spotify_library, "foo": other_library},  # type: ignore[dict-item]
        )

        assert count == 2
        spotify_library.delete_playlist.assert_awaited_once_with(spotify_playlist.provider_id)
        other_library.delete_playlist.assert_awaited_once_with(other_playlist.provider_id)
        assert mock_playlist_repository.delete.await_count == 2

    async def test__purge_remote__remote_failure_skipped(
        self,
        use_case: DeletePlaylistUseCase,
        user: User,
        mock_playlist_repository: mock.AsyncMock,
        mock_provider_library: mock.AsyncMock,
        provider_libraries: dict[MusicProvider, ProviderLibraryPort],
    ) -> None:
        playlists = PlaylistFactory.batch(2, user_id=user.id)
        mock_provider_library.delete_playlist.side_effect = [RuntimeError("network error"), None]

        count = await use_case.purge_remote(playlists=playlists, provider_libraries=provider_libraries)

        assert count == 1
        mock_playlist_repository.delete.assert_awaited_once_with(user_id=user.id, playlist_id=playlists[1].id)

    async def test__purge_remote__missing_library_not_swallowed(
        self,
        use_case: DeletePlaylistUseCase,
        user: User,
        provider_libraries: dict[MusicProvider, ProviderLibraryPort],
    ) -> None:
        playlist = PlaylistFactory.build(user_id=user.id, provider="foo")

        with pytest.raises(KeyError):
            await use_case.purge_remote(playlists=[playlist], provider_libraries=provider_libraries)
