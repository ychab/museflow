import uuid

from museflow.application.ports.unit_of_work import UnitOfWorkPort


async def delete_user(user_id: uuid.UUID, uow: UnitOfWorkPort) -> None:
    async with uow:
        await uow.users.delete(user_id)
