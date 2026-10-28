import uuid

from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.domain.exceptions import BlacklistItemNotFoundError


class RemoveFromBlacklistUseCase:
    def __init__(self, uow: UnitOfWorkPort) -> None:
        self._uow = uow

    async def remove(self, user_id: uuid.UUID, item_ids: list[uuid.UUID]) -> None:
        async with self._uow as uow:
            removed = await uow.blacklist.remove(user_id=user_id, item_ids=item_ids)

        if missing := set(item_ids) - removed:
            raise BlacklistItemNotFoundError(f"{len(missing)} item(s) not found")

    async def purge(self, user_id: uuid.UUID) -> int:
        async with self._uow as uow:
            return await uow.blacklist.purge(user_id=user_id)
