import uuid

from museflow.application.ports.repositories.playlist import PlaylistRepository
from museflow.domain.entities.user import User
from museflow.domain.exceptions import PlaylistNotFoundError
from museflow.domain.types import MusicProvider
from museflow.domain.types import PlaylistType


async def playlist_delete(
    user: User,
    playlist_repository: PlaylistRepository,
    playlist_id: uuid.UUID | None = None,
    purge: bool = False,
    type: PlaylistType | None = None,
    provider: MusicProvider | None = None,
) -> int:
    if purge:
        return await playlist_repository.purge(user_id=user.id, type=type, provider=provider)

    if playlist_id is None:
        raise PlaylistNotFoundError()

    deleted = await playlist_repository.delete(user_id=user.id, playlist_id=playlist_id)
    if not deleted:
        raise PlaylistNotFoundError()
    return 1
