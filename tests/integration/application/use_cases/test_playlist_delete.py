import pytest

from museflow.application.ports.providers.library import ProviderLibraryPort
from museflow.application.ports.repositories.playlist import PlaylistRepository
from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.application.use_cases.playlist_delete import PlaylistDeleteUseCase
from museflow.domain.entities.user import User
from museflow.domain.enums import MusicProvider
from museflow.domain.enums import PlaylistType

from tests.integration.factories.models.playlist import PlaylistModelFactory


class TestPlaylistDeleteUseCase:
    async def test__single_delete__nominal(
        self,
        uow: UnitOfWorkPort,
        user: User,
        playlist_repository: PlaylistRepository,
    ) -> None:
        playlist_db = await PlaylistModelFactory.create_async(user_id=user.id)

        await PlaylistDeleteUseCase(user_id=user.id, uow=uow).delete(playlist_id=playlist_db.id)
        assert await playlist_repository.get(user.id, playlist_db.id) is None

    async def test__purge__nominal(
        self,
        uow: UnitOfWorkPort,
        user: User,
        playlist_repository: PlaylistRepository,
    ) -> None:
        await PlaylistModelFactory.create_async(user_id=user.id)
        await PlaylistModelFactory.create_async(user_id=user.id)

        count = await PlaylistDeleteUseCase(user_id=user.id, uow=uow).purge(type=None, provider=None)

        assert count == 2
        assert await playlist_repository.list(user.id) == []

    @pytest.mark.wiremock("spotify")
    async def test__single_delete__include_remote__nominal(
        self,
        uow: UnitOfWorkPort,
        user: User,
        playlist_repository: PlaylistRepository,
        spotify_library: ProviderLibraryPort,
    ) -> None:
        playlist_db = await PlaylistModelFactory.create_async(user_id=user.id)

        use_case = PlaylistDeleteUseCase(user_id=user.id, uow=uow)
        playlist = await use_case.find(playlist_id=playlist_db.id)
        await use_case.delete_remote(
            playlist=playlist,
            provider_libraries={MusicProvider.SPOTIFY: spotify_library},
        )

        assert await playlist_repository.get(user.id, playlist_db.id) is None

    @pytest.mark.wiremock("spotify")
    async def test__single_delete__include_remote__without_tracks(
        self,
        uow: UnitOfWorkPort,
        user: User,
        playlist_repository: PlaylistRepository,
        spotify_library: ProviderLibraryPort,
    ) -> None:
        playlist_db = await PlaylistModelFactory.create_async(user_id=user.id, track_ids=[])

        use_case = PlaylistDeleteUseCase(user_id=user.id, uow=uow)
        playlist = await use_case.find(playlist_id=playlist_db.id)
        await use_case.delete_remote(
            playlist=playlist,
            provider_libraries={MusicProvider.SPOTIFY: spotify_library},
        )

        assert await playlist_repository.get(user.id, playlist_db.id) is None

    async def test__purge__filtered_by_type(
        self,
        uow: UnitOfWorkPort,
        user: User,
        playlist_repository: PlaylistRepository,
    ) -> None:
        playlist_db = await PlaylistModelFactory.create_async(user_id=user.id, type=PlaylistType.DISCOVERY)

        count = await PlaylistDeleteUseCase(user_id=user.id, uow=uow).purge(
            type=PlaylistType.DISCOVERY,
            provider=None,
        )

        assert count == 1
        assert await playlist_repository.get(user.id, playlist_db.id) is None
