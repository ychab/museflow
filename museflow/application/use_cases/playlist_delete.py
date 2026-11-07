import logging
import uuid
from collections.abc import Mapping

from museflow.application.ports.providers.library import ProviderLibraryPort
from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.domain.entities.playlist import Playlist
from museflow.domain.enums import MusicProvider
from museflow.domain.enums import PlaylistType
from museflow.domain.exceptions import PlaylistNotFoundError

logger = logging.getLogger(__name__)


class DeletePlaylistUseCase:
    """Deletes a user's playlists, locally only or on their provider too.

    For a remote deletion, the caller finds the playlists, builds the library of each of their providers, then passes
    both to `delete_remote` or `purge_remote`: each playlist goes through the library of its own provider.
    """

    def __init__(self, user_id: uuid.UUID, uow: UnitOfWorkPort) -> None:
        self._user_id = user_id
        self._uow = uow

    async def find(self, playlist_id: uuid.UUID) -> Playlist:
        async with self._uow as uow:
            playlist = await uow.playlists.get(user_id=self._user_id, playlist_id=playlist_id)
        if playlist is None:
            raise PlaylistNotFoundError()

        return playlist

    async def find_matching(self, type: PlaylistType | None, provider: MusicProvider | None) -> list[Playlist]:
        async with self._uow as uow:
            playlists = await uow.playlists.get_list(user_id=self._user_id)

        return [
            p for p in playlists if (type is None or p.type == type) and (provider is None or p.provider == provider)
        ]

    async def delete(self, playlist_id: uuid.UUID) -> None:
        async with self._uow as uow:
            deleted = await uow.playlists.delete(user_id=self._user_id, playlist_id=playlist_id)
        if not deleted:
            raise PlaylistNotFoundError()

    async def delete_remote(
        self,
        playlist: Playlist,
        provider_libraries: Mapping[MusicProvider, ProviderLibraryPort],
    ) -> None:
        await provider_libraries[playlist.provider].delete_playlist(playlist.provider_id)
        await self.delete(playlist.id)

    async def purge(self, type: PlaylistType | None, provider: MusicProvider | None) -> int:
        async with self._uow as uow:
            return await uow.playlists.purge(user_id=self._user_id, type=type, provider=provider)

    async def purge_remote(
        self,
        playlists: list[Playlist],
        provider_libraries: Mapping[MusicProvider, ProviderLibraryPort],
    ) -> int:
        count = 0
        for playlist in playlists:
            provider_library = provider_libraries[playlist.provider]
            try:
                await provider_library.delete_playlist(playlist.provider_id)
            except Exception:
                logger.warning(
                    f"Failed to delete remote playlist '{playlist.name}'",
                    extra={"playlist_id": str(playlist.id)},
                )
                continue

            async with self._uow as uow:
                await uow.playlists.delete(user_id=self._user_id, playlist_id=playlist.id)

            count += 1

        return count
