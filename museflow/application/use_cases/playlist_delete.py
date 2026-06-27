import logging
import uuid

from museflow.application.ports.providers.library import ProviderLibraryPort
from museflow.application.ports.repositories.playlist import PlaylistRepository
from museflow.domain.entities.user import User
from museflow.domain.exceptions import PlaylistNotFoundError
from museflow.domain.types import MusicProvider
from museflow.domain.types import PlaylistType

logger = logging.getLogger(__name__)


class PlaylistDeleteUseCase:
    def __init__(
        self,
        playlist_repository: PlaylistRepository,
        provider_library: ProviderLibraryPort | None = None,
    ) -> None:
        self._playlist_repository = playlist_repository
        self._provider_library = provider_library

    async def delete(self, user: User, playlist_id: uuid.UUID, include_remote: bool = False) -> None:
        if include_remote and self._provider_library is None:
            raise ValueError("provider_library is required when include_remote=True")

        if include_remote:
            playlist = await self._playlist_repository.get(user_id=user.id, playlist_id=playlist_id)
            if playlist is None:
                raise PlaylistNotFoundError()

            await self._provider_library.delete_playlist(playlist.provider_id)  # type: ignore[union-attr]

        deleted = await self._playlist_repository.delete(user_id=user.id, playlist_id=playlist_id)
        if not deleted:
            raise PlaylistNotFoundError()

        return

    async def purge(
        self,
        user: User,
        type: PlaylistType | None = None,
        provider: MusicProvider | None = None,
        include_remote: bool = False,
    ) -> int:
        if include_remote and self._provider_library is None:
            raise ValueError("provider_library is required when include_remote=True")

        if not include_remote:
            return await self._playlist_repository.purge(user_id=user.id, type=type, provider=provider)

        playlists = await self._playlist_repository.list(user_id=user.id)
        matching = [
            p for p in playlists if (type is None or p.type == type) and (provider is None or p.provider == provider)
        ]

        count = 0
        for playlist in matching:
            try:
                await self._provider_library.delete_playlist(playlist.provider_id)  # type: ignore[union-attr]
            except Exception:
                logger.warning(
                    f"Failed to delete remote playlist '{playlist.name}'",
                    extra={"playlist_id": str(playlist.id)},
                )
                continue
            await self._playlist_repository.delete(user_id=user.id, playlist_id=playlist.id)
            count += 1
        return count
