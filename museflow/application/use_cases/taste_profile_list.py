import uuid

from museflow.application.outputs.pagination import Page
from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.domain.entities.taste import TasteProfile


async def get_taste_profiles(
    user_id: uuid.UUID,
    uow: UnitOfWorkPort,
    limit: int | None = None,
    offset: int = 0,
) -> Page[TasteProfile]:
    async with uow:
        taste_profiles = await uow.taste_profiles.get_list(user_id=user_id, limit=limit, offset=offset)
        total = await uow.taste_profiles.count(user_id=user_id)

    return Page(items=taste_profiles, total=total, limit=limit, offset=offset)
