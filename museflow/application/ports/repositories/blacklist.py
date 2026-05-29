import uuid
from abc import ABC
from abc import abstractmethod

from museflow.domain.entities.blacklist import BlacklistedArtist
from museflow.domain.entities.blacklist import BlacklistedTrack
from museflow.domain.value_objects.blacklist import UserBlacklist


class BlacklistRepository(ABC):
    """Port for persisting and querying user blacklist entries."""

    @abstractmethod
    async def add_artist(self, user_id: uuid.UUID, artist_name: str) -> BlacklistedArtist: ...

    @abstractmethod
    async def add_track(self, user_id: uuid.UUID, name: str, artist_name: str) -> BlacklistedTrack: ...

    @abstractmethod
    async def remove(self, user_id: uuid.UUID, item_ids: list[uuid.UUID]) -> set[uuid.UUID]:
        """Remove blacklist entries by ID. Returns the set of IDs that were actually deleted."""
        ...

    @abstractmethod
    async def purge(self, user_id: uuid.UUID) -> int:
        """Delete all blacklist entries for the user. Returns the total number of deleted rows."""
        ...

    @abstractmethod
    async def get_all_for_user(self, user_id: uuid.UUID) -> UserBlacklist: ...
