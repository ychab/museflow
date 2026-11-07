import uuid

from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.domain.entities.taste import TasteProfile


async def get_taste_profiles(
    user_id: uuid.UUID,
    uow: UnitOfWorkPort,
) -> list[TasteProfile]:
    async with uow:
        return await uow.taste_profiles.get_list(user_id=user_id)
