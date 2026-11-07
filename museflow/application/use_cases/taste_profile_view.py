import uuid

from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.domain.entities.taste import TasteProfile
from museflow.domain.exceptions import TasteProfileNotFoundError


async def get_taste_profile(
    user_id: uuid.UUID,
    name: str,
    uow: UnitOfWorkPort,
) -> TasteProfile:
    async with uow:
        taste_profile = await uow.taste_profiles.get(user_id=user_id, name=name)

    if not taste_profile:
        raise TasteProfileNotFoundError()

    return taste_profile
