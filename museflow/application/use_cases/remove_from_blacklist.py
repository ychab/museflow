import uuid

from museflow.application.ports.repositories.blacklist import BlacklistRepository
from museflow.domain.exceptions import BlacklistItemNotFoundError


class RemoveFromBlacklistUseCase:
    def __init__(self, blacklist_repository: BlacklistRepository) -> None:
        self._blacklist_repository = blacklist_repository

    async def remove(self, user_id: uuid.UUID, item_ids: list[uuid.UUID]) -> None:
        removed = await self._blacklist_repository.remove(user_id=user_id, item_ids=item_ids)

        if missing := set(item_ids) - removed:
            raise BlacklistItemNotFoundError(f"{len(missing)} item(s) not found")

    async def purge(self, user_id: uuid.UUID) -> int:
        return await self._blacklist_repository.purge(user_id=user_id)
