import uuid

from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.domain.value_objects.blacklist import UserBlacklist


async def list_blacklist(user_id: uuid.UUID, uow: UnitOfWorkPort) -> UserBlacklist:
    async with uow:
        return await uow.blacklist.get_all(user_id=user_id)
