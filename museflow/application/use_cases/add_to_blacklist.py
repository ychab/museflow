import uuid

from museflow.application.ports.repositories.blacklist import BlacklistRepository
from museflow.domain.entities.blacklist import BlacklistedArtist
from museflow.domain.entities.blacklist import BlacklistedTrack


class AddToBlacklistUseCase:
    def __init__(self, blacklist_repository: BlacklistRepository) -> None:
        self._blacklist_repository = blacklist_repository

    async def add_artist(self, user_id: uuid.UUID, artist_name: str) -> BlacklistedArtist:
        return await self._blacklist_repository.add_artist(user_id=user_id, artist_name=artist_name)

    async def add_track(self, user_id: uuid.UUID, name: str, artist_name: str) -> BlacklistedTrack:
        return await self._blacklist_repository.add_track(user_id=user_id, name=name, artist_name=artist_name)
