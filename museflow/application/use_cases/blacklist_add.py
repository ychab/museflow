import uuid

from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.domain.entities.blacklist import BlacklistedArtist
from museflow.domain.entities.blacklist import BlacklistedTrack


class AddToBlacklistUseCase:
    def __init__(self, uow: UnitOfWorkPort) -> None:
        self._uow = uow

    async def add_artist(self, user_id: uuid.UUID, artist_name: str) -> BlacklistedArtist:
        async with self._uow as uow:
            return await uow.blacklist.add_artist(user_id=user_id, artist_name=artist_name)

    async def add_track(self, user_id: uuid.UUID, name: str, artist_name: str) -> BlacklistedTrack:
        async with self._uow as uow:
            return await uow.blacklist.add_track(user_id=user_id, name=name, artist_name=artist_name)
